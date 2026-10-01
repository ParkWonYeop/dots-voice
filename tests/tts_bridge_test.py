import asyncio
import time
import numpy as np
from types import SimpleNamespace
from tts_bridge_server import Engine,SpeechTrack
from audio_stream import PcmResampler,PauseLimiter

def test_continuous_resampling():
    # A nonzero waveform at arbitrary boundaries exposes zero-padding clicks.
    x=(0.2*np.sin(2*np.pi*337.3*np.arange(24000)/24000)).astype(np.float32)
    whole=PcmResampler();expected=np.concatenate(whole.push(x,24000)+whole.finish())
    streaming=PcmResampler();pieces=[]
    for start in range(0,len(x),769):pieces.extend(streaming.push(x[start:start+769],24000))
    actual=np.concatenate(pieces+streaming.finish())
    assert len(actual)==48000 and np.allclose(actual,expected,atol=1e-7), 'Chunk boundaries must not alter the resampled waveform'

def test_pause_limiter():
    speech=np.full(4800,0.02,dtype=np.float32);short=np.zeros(4800,dtype=np.float32)
    long=np.zeros(48000,dtype=np.float32)
    x=np.concatenate((speech,short,speech,long,speech))
    limiter=PauseLimiter();pieces=[]
    for start in range(0,len(x),797):pieces.append(limiter.push(x[start:start+797]))
    pieces.append(limiter.push(np.empty(0,dtype=np.float32),final=True))
    expected=np.concatenate((speech,short,speech,long[:11520],speech))
    assert np.array_equal(np.concatenate(pieces),expected), 'Preserve words and 100ms closures; cap a one-second silence at 240ms across chunks'
    guarded=PauseLimiter()
    assert np.array_equal(guarded.push(long,max_remove_samples=0),long), 'Keep the available audio when inference has no playback lead'
    assert len(guarded.push(long,max_remove_samples=480))==47520, 'Never trim more than the safe playback budget'

def test_selected_design():
    config={'modelDirectory':'unused','mode':'voice_design','speaker':'designed_soft','style':'designed_soft',
            'language':'Korean','temperature':0.8,'streamingInterval':0.64,
            'styles':{'designed_soft':'The exact instruction used for the selected second sample.'}}
    engine=Engine(config);calls=[]
    class Model:
        def generate_voice_design(self,**kwargs):
            calls.append(kwargs)
            return iter([SimpleNamespace(audio=np.ones(24,dtype=np.float32),sample_rate=24000)])
        def generate_custom_voice(self,**kwargs):
            raise AssertionError('Selected designed voice must use the sample generation method')
    engine.model=Model()
    try:
        list(engine.synthesize('첫 답변'));list(engine.synthesize('다른 내용의 두 번째 답변'))
        assert all(c['instruct']==config['styles']['designed_soft'] for c in calls), 'Reuse the chosen sample instruction across replies'
        assert all(c['language']=='Korean' for c in calls)
        assert all(c['stream'] and c['streaming_interval']==0.64 and 'speaker' not in c for c in calls)
    finally:engine.executor.shutdown(wait=True)

def test_selected_reference():
    config={'modelDirectory':'unused','mode':'speaker_reference','language':'Korean',
            'temperature':0.7,'streamingInterval':0.32}
    engine=Engine(config);calls=[];engine.reference=np.ones(240,dtype=np.float32)
    class Model:
        def generate(self,**kwargs):calls.append(kwargs);return iter(())
    engine.model=Model()
    try:
        for text in ('첫 번째 문장이에요.','이번에는 질문해도 될까?'):list(engine.synthesize(text))
        assert all(c['ref_audio'] is engine.reference for c in calls)
        assert all('ref_text' not in c and 'instruct' not in c for c in calls), 'Reuse identity without imposing reference delivery'
        assert all(c['split_pattern']=='' and c['streaming_interval']==0.32 for c in calls)
    finally:engine.shutdown()

def fake_worker(connection,cancel,config):
    connection.send(('ready',None))
    while True:
        text=connection.recv()
        if text is None:break
        for _ in range(4):
            if cancel.is_set():break
            connection.send(('pcm',np.full(960,0.1,dtype=np.float32)))
            time.sleep(0.02)
        connection.send(('done',{'text':text}))
    connection.close()

def test_process_interruption():
    from tts_worker import ProcessEngine
    engine=ProcessEngine({},worker=fake_worker);chunks=[]
    try:
        engine.executor.submit(engine.initialize).result(timeout=15)
        result=engine.executor.submit(engine.generate,'cancelled',chunks.append,lambda:bool(chunks)).result(timeout=5)
        assert result is None and len(chunks)==1, 'Cancel and drain old worker response'
        chunks.clear()
        result=engine.executor.submit(engine.generate,'new reply',chunks.append,lambda:False).result(timeout=5)
        assert result=={'text':'new reply'} and len(chunks)==4, 'Next reply must not inherit old PCM or cancellation'
    finally:engine.shutdown()
    assert not engine.process.is_alive()

async def main():
    test_selected_design()
    test_selected_reference()
    test_continuous_resampling()
    test_pause_limiter()
    test_process_interruption()
    track=SpeechTrack(None,{'flushes':0,'outputPeak':0,'outputSamples':0},False)
    track.worker.cancel()
    track.current=np.full(1920,0.1,dtype=np.float32)
    track.started=time.monotonic();track.pts=4800
    pending=asyncio.create_task(track.recv())
    await asyncio.sleep(0.02);track.flush()
    frame=await asyncio.wait_for(pending,1)
    assert frame.samples==960 and not frame.to_ndarray().any()
    track.enqueue(track.epoch,np.full(1920,0.2,dtype=np.float32))
    resumed=await asyncio.wait_for(track.recv(),1)
    assert resumed.samples==960 and resumed.to_ndarray().any()
    track.enqueue(track.epoch-1,np.ones(960,dtype=np.float32))
    assert not track.audio
    track.stop()
    class BufferedEngine:config={'playbackBufferSeconds':3.2}
    buffered=SpeechTrack(BufferedEngine(),{'flushes':0,'outputPeak':0,'outputSamples':0},False)
    buffered.worker.cancel();buffered.generating=True
    buffered.enqueue(buffered.epoch,np.full(30720*4,0.1,dtype=np.float32))
    first=await buffered.recv()
    assert not first.to_ndarray().any(), 'Wait for the configured buffer before playback'
    buffered.enqueue(buffered.epoch,np.full(30720,0.1,dtype=np.float32))
    second=await buffered.recv()
    assert second.to_ndarray().any(), 'Play when the initial buffer is ready'
    buffered.flush();buffered.enqueue(buffered.epoch,np.full(960,0.2,dtype=np.float32))
    buffered.generating=False
    short=await buffered.recv()
    assert short.to_ndarray().any(), 'A completed short utterance must not wait forever'
    buffered.stop()
    direct=SpeechTrack(None,{'flushes':0,'outputPeak':0,'outputSamples':0},False)
    direct.worker.cancel();direct.generating=True
    direct.enqueue(direct.epoch,np.full(960,0.1,dtype=np.float32))
    assert (await direct.recv()).to_ndarray().any(), 'Default playback adds no prebuffer delay'
    assert not (await direct.recv()).to_ndarray().any()
    assert not (await direct.recv()).to_ndarray().any()
    assert direct.stats['underflows']==1, 'Count a starvation episode once'
    direct.enqueue(direct.epoch,np.full(960,0.1,dtype=np.float32))
    assert (await direct.recv()).to_ndarray().any(), 'Resume immediately without refilling a large buffer'
    direct.stop()
    print('TTS buffering, short utterances and flush regression passed')
if __name__=='__main__':asyncio.run(main())
