"""Loopback-only, assistant text in / Korean TTS audio out over WebRTC."""
import argparse
import asyncio
import concurrent.futures
import hashlib
import json
import os
import secrets
import time
from collections import deque
from fractions import Fraction
from pathlib import Path
import av
import numpy as np
import soundfile as sf
from audio_stream import PcmResampler,PauseLimiter
from aiohttp import web
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCConfiguration, RTCSessionDescription

ROOT=Path(__file__).resolve().parents[1]


class Engine:
    def __init__(self,config=None):
        self.config=config if config is not None else json.loads((ROOT/'config/voice_settings.json').read_text())
        self.model_directory=ROOT/self.config['modelDirectory']
        self.model=None;self.streams=[]
        self.executor=concurrent.futures.ThreadPoolExecutor(max_workers=1,thread_name_prefix='dots-mlx')
    def initialize(self):
        from mlx_audio.tts.utils import load_model
        import mlx.core as mx
        # MLX streams are thread-local: load, cached arrays and inference belong
        # to the same dedicated worker, as in mlx_audio's voice pipeline.
        self.streams=[mx.new_stream(mx.cpu),mx.new_stream(mx.gpu)]
        for stream in self.streams:mx.set_default_stream(stream)
        self.model=load_model(self.model_directory)
        self.reference=None
        if self.config.get('mode')=='speaker_reference':
            path=ROOT/self.config['referenceAudio']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=self.config['referenceSha256']:
                raise ValueError('Selected voice reference has changed')
            pcm,rate=sf.read(path,dtype='float32')
            if rate!=self.model.sample_rate or pcm.ndim!=1 or not np.isfinite(pcm).all():
                raise ValueError('Invalid selected voice reference')
            self.reference=mx.array(pcm);mx.eval(self.reference)
    def synthesize(self,text):
        config=self.config
        options={'text':text,'temperature':config['temperature'],'max_tokens':1024,
                 'stream':True,'streaming_interval':config['streamingInterval']}
        if config.get('mode')=='speaker_reference':
            # Only condition on the selected sample's speaker identity. Supplying
            # ref_text would select ICL and copy the reference's speaking rhythm.
            return self.model.generate(**options,lang_code=config['language'],
                ref_audio=self.reference,split_pattern='',repetition_penalty=config.get('repetitionPenalty',1.05))
        if config.get('mode')=='voice_design':
            return self.model.generate_voice_design(**options,language=config['language'],
                instruct=config['styles'][config['style']])
        return self.model.generate_custom_voice(**options,speaker=config['speaker'],
            language=config['language'],instruct=config['styles'][config['style']])
    def generate(self,text,emit,cancelled):
        import mlx.core as mx
        config=self.config;mx.random.seed(config['seed']);started=time.perf_counter();first=None;chunks=[]
        resampler=PcmResampler();raw_samples=0;emitted_samples=0
        limiter=PauseLimiter(config['maxPauseSeconds'],config.get('silenceThreshold',0.002)) if config.get('maxPauseSeconds') else None
        def output(pcm):
            nonlocal first,emitted_samples
            if not len(pcm):return
            if first is None:first=(time.perf_counter()-started)*1000
            emitted_samples+=len(pcm);chunks.append(pcm);emit(pcm)
        def resampled(pcm):
            nonlocal raw_samples
            raw_samples+=len(pcm)
            if limiter:
                # Trimming must not consume the lead needed to generate the next
                # chunk. This retains quiet PCM under load, without delaying start.
                ready=(len(pcm)+len(limiter.pending))//limiter.frame_size*limiter.frame_size
                elapsed=max(0,time.perf_counter()-started-(first or 0)/1000)
                budget=max(0,int(emitted_samples+ready-48000*(elapsed+config['streamingInterval']))) if first is not None else 0
                pcm=limiter.push(pcm,max_remove_samples=budget)
            output(pcm)
        for r in self.synthesize(text):
            if cancelled():return None
            pcm=np.asarray(r.audio,dtype=np.float32)
            if not np.isfinite(pcm).all():raise ValueError('Non-finite TTS output')
            for piece in resampler.push(pcm,r.sample_rate):resampled(piece)
        if cancelled():return None
        for piece in resampler.finish():resampled(piece)
        if limiter:output(limiter.push(np.empty(0,dtype=np.float32),final=True))
        seconds=sum(len(x) for x in chunks)/48000
        return {'firstChunkMs':round(first or 0,1),'generatedSeconds':seconds,
                'rawGeneratedSeconds':raw_samples/48000,'removedSilenceSeconds':round(raw_samples/48000-seconds,3),
                'generationMs':round((time.perf_counter()-started)*1000,1)}
    def shutdown(self):
        self.executor.shutdown(wait=True,cancel_futures=True)


def create_engine(config):
    if config.get('backend', 'mlx') == 'torch':
        from tts_torch_engine import TorchEngine
        return TorchEngine(config)
    if config.get('backend', 'mlx') != 'mlx':
        raise ValueError('Unknown TTS backend')
    return Engine(config)


class SpeechTrack(MediaStreamTrack):
    kind='audio'
    def __init__(self,engine,stats,record):
        super().__init__();self.engine=engine;self.stats=stats;self.record=record
        self.jobs=asyncio.Queue(maxsize=16);self.audio=deque();self.current=np.empty(0,dtype=np.float32)
        self.queued_samples=0;self.generating=False;self.buffering=True;self.playing=False
        self.buffer_samples=int(48000*(engine.config.get('playbackBufferSeconds',0) if engine else 0))
        self.epoch=0;self.pts=0;self.started=None;self.stopped=False;self.channel=None;self.recordings=[]
        self.loop=asyncio.get_running_loop();self.worker=asyncio.create_task(self.work())
    def notify(self,message):
        if self.channel and self.channel.readyState=='open':self.channel.send(json.dumps(message))
    def flush(self,count=True):
        self.epoch+=1;self.audio.clear();self.current=np.empty(0,dtype=np.float32)
        self.queued_samples=0;self.buffering=True;self.playing=False
        while not self.jobs.empty():self.jobs.get_nowait()
        if count:self.stats['flushes']+=1
    def enqueue(self,epoch,pcm):
        if epoch==self.epoch and not self.stopped:
            self.audio.append(pcm);self.queued_samples+=len(pcm)
    async def work(self):
        while True:
            epoch,identifier,text,received=await self.jobs.get()
            if epoch!=self.epoch:continue
            enqueued=time.perf_counter();audio=[]
            def emit(pcm):
                if not audio:self.loop.call_soon_threadsafe(self.notify,{'type':'audio_started','id':identifier,
                    'firstAudioMs':round((time.perf_counter()-received)*1000,1),
                    'queueMs':round((enqueued-received)*1000,1)})
                audio.append(pcm)
                self.loop.call_soon_threadsafe(self.enqueue,epoch,pcm)
            try:
                self.generating=True
                result=await self.loop.run_in_executor(self.engine.executor,self.engine.generate,text,emit,
                    lambda:epoch!=self.epoch or self.stopped)
                if result is not None and epoch==self.epoch:
                    result['queueMs']=round((enqueued-received)*1000,1)
                    self.stats['phrases']+=1;self.stats['lastGeneration']=result
                    self.stats['generatedSeconds']+=result['generatedSeconds']
                    self.stats['lastJobMs']=round((time.perf_counter()-enqueued)*1000,1)
                    if self.record and audio:
                        sf.write(ROOT/f'artifacts/tts-live-{identifier}.wav',np.concatenate(audio),48000)
                    self.notify({'type':'generated','id':identifier,**result})
            except asyncio.CancelledError:raise
            except Exception as error:
                self.stats['error']=str(error);self.notify({'type':'error','message':str(error)})
            finally:self.generating=False
    async def recv(self):
        if self.started is None:self.started=time.monotonic()
        available=len(self.current)+self.queued_samples
        waiting=self.generating or not self.jobs.empty()
        if not available:
            if self.playing and waiting:self.stats['underflows']=self.stats.get('underflows',0)+1
            self.buffering=True;self.playing=False
        if self.buffering and available and (available>=self.buffer_samples or not waiting):
            self.buffering=False;self.playing=True
        chunk=np.zeros(960,dtype=np.float32)
        if not self.buffering:
            while len(self.current)<960 and self.audio:
                pcm=self.audio.popleft();self.queued_samples-=len(pcm)
                self.current=np.concatenate((self.current,pcm))
            size=min(960,len(self.current));chunk[:size]=self.current[:size];self.current=self.current[size:]
        epoch=self.epoch
        await asyncio.sleep(max(0,self.started+self.pts/48000-time.monotonic()))
        if epoch!=self.epoch:chunk.fill(0)
        self.stats['outputPeak']=max(self.stats['outputPeak'],float(np.abs(chunk).max()))
        self.stats['outputSamples']+=960
        f=av.AudioFrame.from_ndarray((np.clip(chunk,-1,1)*32767).astype(np.int16)[None],format='s16',layout='mono')
        f.sample_rate=48000;f.time_base=Fraction(1,48000);f.pts=self.pts;self.pts+=960
        return f
    def stop(self):
        if self.stopped:return
        self.stopped=True;self.flush(count=False);self.worker.cancel();super().stop()


async def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8766)
    parser.add_argument('--in-process',action='store_true',help='Compare inference in the RTC process')
    parser.add_argument('--record-test',action='store_true');args=parser.parse_args()
    (ROOT/'runtime').mkdir(exist_ok=True);(ROOT/'artifacts').mkdir(exist_ok=True)
    from tts_worker import ProcessEngine
    settings_bytes=(ROOT/'config/voice_settings.json').read_bytes()
    config=json.loads(settings_bytes)
    engine=create_engine(config) if args.in_process else ProcessEngine(config)
    loop=asyncio.get_running_loop()
    await loop.run_in_executor(engine.executor,engine.initialize)
    if args.in_process:await loop.run_in_executor(engine.executor,engine.generate,'안녕!',lambda pcm:None,lambda:False)
    token=secrets.token_urlsafe(24);peers=set()
    from voice_launcher import SERVICE,root_id
    stats={'service':SERVICE,'rootId':root_id(),'configDigest':hashlib.sha256(settings_bytes).hexdigest(),
           'style':engine.config['style'],'speaker':engine.config['speaker'],
           'mode':engine.config.get('mode','custom_voice'),'model':engine.config['model'],'phrases':0,
           'flushes':0,'generatedSeconds':0,'outputSamples':0,'outputPeak':0,'underflows':0,
           'playbackBufferSeconds':engine.config.get('playbackBufferSeconds',0),'error':None}
    stats['inferenceProcess']='shared' if args.in_process else 'separate'
    stats['backend']=config.get('backend','mlx')
    stats['device']=config.get('device','apple-gpu')
    stats['synthesisMode']='phrase' if config.get('backend')=='torch' else 'streaming'
    stats['maxPauseSeconds']=engine.config.get('maxPauseSeconds')
    config_path=ROOT/'runtime/tts-bridge-config.json'
    fd=os.open(config_path,os.O_CREAT|os.O_WRONLY|os.O_TRUNC,0o600)
    os.chmod(config_path,0o600)
    with os.fdopen(fd,'w') as output:json.dump({'url':f'http://127.0.0.1:{args.port}/offer?token={token}'},output)
    (ROOT/'runtime/install-tts.js').write_text((ROOT/'chrome-extension/transcript_buffer.js').read_text(encoding='utf-8')+'\n'+(ROOT/'chrome-extension/dots-tts.js').read_text(encoding='utf-8'),encoding='utf-8')
    async def offer(request):
        if request.headers.get('Authorization')!='Bearer '+token:raise web.HTTPForbidden()
        data=await request.json();pc=RTCPeerConnection(RTCConfiguration(iceServers=[]));peers.add(pc)
        track=SpeechTrack(engine,stats,args.record_test);pc.addTrack(track)
        @pc.on('datachannel')
        def onchannel(channel):
            track.channel=channel
            @channel.on('message')
            def message(message):
                try:
                    command=json.loads(message)
                    if command.get('type')=='flush':track.flush()
                    elif command.get('type')=='status':track.notify({'type':'metrics',**stats})
                    elif command.get('type')=='speak':
                        text=command.get('text','').strip();identifier=command.get('id','')
                        if not text or len(text)>300 or not identifier.isalnum():raise ValueError('Invalid text job')
                        track.jobs.put_nowait((track.epoch,identifier,text,time.perf_counter()))
                except (ValueError,TypeError,asyncio.QueueFull) as error:track.notify({'type':'error','message':str(error)})
        @pc.on('connectionstatechange')
        async def changed():
            stats['connection']=pc.connectionState
            if pc.connectionState in ('closed','failed'):
                track.stop();peers.discard(pc)
                (ROOT/'artifacts/tts-live-stats.json').write_text(json.dumps(stats,indent=2))
                if pc.connectionState=='failed':await pc.close()
        await pc.setRemoteDescription(RTCSessionDescription(sdp=data['sdp'],type=data['type']))
        await pc.setLocalDescription(await pc.createAnswer())
        return web.json_response({'type':pc.localDescription.type,'sdp':pc.localDescription.sdp})
    stopped=asyncio.Event()
    async def shutdown(request):
        if request.headers.get('Authorization')!='Bearer '+token:raise web.HTTPForbidden()
        loop.call_later(.2,stopped.set)
        return web.json_response({'stopping':True})
    app=web.Application();app.router.add_post('/offer',offer)
    app.router.add_get('/health',lambda request:web.json_response(stats))
    app.router.add_post('/shutdown',shutdown)
    runner=web.AppRunner(app);await runner.setup();await web.TCPSite(runner,'127.0.0.1',args.port).start()
    print(json.dumps({'ready':True,'listen':f'127.0.0.1:{args.port}',**stats}),flush=True)
    try:await stopped.wait()
    finally:
        await asyncio.gather(*(pc.close() for pc in list(peers)),return_exceptions=True)
        await runner.cleanup();engine.shutdown()


if __name__=='__main__':
    try:asyncio.run(main())
    except KeyboardInterrupt:pass
