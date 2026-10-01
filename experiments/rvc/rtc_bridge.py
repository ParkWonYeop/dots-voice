"""WebRTC transport for the local RVC engine. Signalling stays in local files."""
import asyncio
import json
import time
from collections import deque
from fractions import Fraction
from pathlib import Path
import numpy as np
import av
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription, RTCConfiguration
from aiortc.mediastreams import MediaStreamError

ROOT=Path(__file__).resolve().parent


class ConvertedTrack(MediaStreamTrack):
    kind='audio'
    def __init__(self,source,engine,stats,record):
        super().__init__()
        self.source=source;self.engine=engine;self.stats=stats;self.record=record
        self.queue=asyncio.Queue(maxsize=30)
        self.output=np.empty(0,dtype=np.float32)
        self.pending=np.empty(0,dtype=np.float32)
        self.history=np.zeros(30720,dtype=np.float32)
        self.tail=None;self.epoch=0;self.pts=0;self.started=None
        self.input_record=[];self.output_record=[]
        self.worker=asyncio.create_task(self.convert_loop())
    def flush(self):
        self.epoch+=1;self.pending=np.empty(0,dtype=np.float32);self.output=np.empty(0,dtype=np.float32)
        self.history.fill(0);self.tail=None
        while not self.queue.empty():self.queue.get_nowait()
        self.stats['flushes']=self.stats.get('flushes',0)+1
    async def convert_loop(self):
        resampler=av.AudioResampler(format='flt',layout='mono',rate=48000)
        block=15360;ahead=1920
        try:
            while True:
                frame=await self.source.recv()
                for f in resampler.resample(frame):
                    pcm=f.to_ndarray().reshape(-1).astype(np.float32)
                    self.pending=np.concatenate((self.pending,pcm))
                while len(self.pending)>=block+ahead:
                    epoch=self.epoch
                    chunk=self.pending[:block].copy()
                    source=np.concatenate((self.history,self.pending[:block+ahead]))
                    if np.sqrt(np.mean(source**2))<0.0001:
                        converted=np.zeros_like(source);elapsed=0.
                    else:converted,elapsed=await asyncio.to_thread(self.engine.convert,source,48000)
                    if epoch!=self.epoch:continue
                    output=converted[len(self.history):len(self.history)+block].copy()
                    if self.tail is not None:
                        fade=np.linspace(0,1,ahead,dtype=np.float32)
                        output[:ahead]=self.tail*(1-fade)+output[:ahead]*fade
                    self.tail=converted[len(self.history)+block:len(self.history)+block+ahead].copy()
                    self.history=np.concatenate((self.history,chunk))[-len(self.history):]
                    self.pending=self.pending[block:]
                    self.stats['rtcBlocks']=self.stats.get('rtcBlocks',0)+1
                    self.stats['rtcInferenceMs']=round(elapsed,2)
                    self.stats.setdefault('rtcInferenceHistory',[]).append(round(elapsed,2))
                    self.stats['rtcInferenceHistory']=self.stats['rtcInferenceHistory'][-200:]
                    self.stats['rtcInputRms']=float(np.sqrt(np.mean(chunk**2)))
                    self.stats['rtcOutputRms']=float(np.sqrt(np.mean(output**2)))
                    self.stats['rtcInputPeak']=max(self.stats.get('rtcInputPeak',0),float(np.max(np.abs(chunk))))
                    self.stats['rtcOutputPeak']=max(self.stats.get('rtcOutputPeak',0),float(np.max(np.abs(output))))
                    if self.record and sum(len(x) for x in self.input_record)<48000*120:
                        self.input_record.append(chunk);self.output_record.append(output)
                    await self.queue.put(output)
        except (MediaStreamError,asyncio.CancelledError):pass
        except Exception as error:self.stats['rtcError']=str(error)
    async def recv(self):
        while len(self.output)<960:
            self.output=np.concatenate((self.output,await self.queue.get()))
        if self.started is None:self.started=time.monotonic()
        # flush() may run while the frame is waiting for its playback deadline.
        # Reserve a full frame first; cancel its old audio with silence, never an
        # empty frame (which terminates aiortc's RTP sender).
        epoch=self.epoch
        chunk=self.output[:960].copy();self.output=self.output[960:]
        await asyncio.sleep(max(0,self.started+self.pts/48000-time.monotonic()))
        if epoch!=self.epoch:chunk=np.zeros(960,dtype=np.float32)
        frame=av.AudioFrame.from_ndarray((np.clip(chunk,-1,1)*32767).astype(np.int16)[None],format='s16',layout='mono')
        frame.sample_rate=48000;frame.time_base=Fraction(1,48000);frame.pts=self.pts;self.pts+=960
        self.stats['rtcOutputSamples']=self.pts
        return frame
    def stop(self):
        self.worker.cancel();super().stop()
        if self.input_record:
            import soundfile as sf
            stamp=int(time.time())
            sf.write(ROOT/f'artifacts/rtc-dot-input-{stamp}.wav',np.concatenate(self.input_record),48000)
            sf.write(ROOT/f'artifacts/rtc-dot-yui-{stamp}.wav',np.concatenate(self.output_record),48000)
            self.input_record=[];self.output_record=[]


async def accept_offer(offer,engine,stats,record,peers):
    pc=RTCPeerConnection(RTCConfiguration(iceServers=[]));peers.add(pc)
    tracks=[]
    channel_holder={}
    @pc.on('track')
    def received(track):
        if track.kind=='audio':
            converted=ConvertedTrack(track,engine,stats,record);tracks.append(converted);pc.addTrack(converted)
    @pc.on('datachannel')
    def channel_received(channel):
        channel_holder['channel']=channel
        @channel.on('message')
        def message_received(message):
            try:
                data=json.loads(message)
                if data.get('type')=='flush':
                    for track in tracks:track.flush()
                elif data.get('type')=='status':channel.send(json.dumps({'type':'metrics',**stats}))
            except (ValueError,TypeError):pass
    @pc.on('connectionstatechange')
    async def connection_changed():
        stats['rtcConnectionState']=pc.connectionState
        if pc.connectionState in ('failed','closed'):
            for track in tracks:track.stop()
            peers.discard(pc)
            (ROOT/'artifacts/rtc-stats.json').write_text(json.dumps(stats,indent=2))
            if pc.connectionState=='failed':await pc.close()
    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer['sdp'],type=offer['type']))
    await pc.setLocalDescription(await pc.createAnswer())
    return {'sdp':pc.localDescription.sdp,'type':pc.localDescription.type}
