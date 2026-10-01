"""Korean prosody A/B sample on Apple Silicon, independent of the dots call."""
import json
import argparse
import time
from pathlib import Path
import numpy as np
import soundfile as sf
from huggingface_hub import snapshot_download
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tts_bridge_server import Engine

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'config/voice_settings.json').read_text())
MODEL=CONFIG['model']
REVISION=CONFIG['revision']
TEXT='안녕! 오늘 하루는 어땠어요? 저는 지금 목소리 테스트를 하고 있어요. 조금 더 밝고 편하게 이야기해 볼게요!'
STYLES=CONFIG['styles']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--styles',default=CONFIG['style'])
    parser.add_argument('--text',default=TEXT)
    args=parser.parse_args()
    labels=args.styles.split(',')
    if any(label not in STYLES for label in labels):parser.error('Unknown voice style for this model')
    if CONFIG.get('mode')=='speaker_reference' and labels!=[CONFIG['style']]:
        parser.error('Reference mode uses the selected reference voice; use voice_candidates.py for other styles')
    destination=ROOT/CONFIG['modelDirectory']
    print('Downloading/loading Qwen3-TTS Korean expressive voice',flush=True)
    snapshot_download(MODEL,revision=REVISION,local_dir=destination)
    engine=Engine();engine.executor.submit(engine.initialize).result()
    engine.executor.submit(engine.generate,'안녕!',lambda pcm:None,lambda:False).result()
    (ROOT/'artifacts').mkdir(exist_ok=True)
    print(json.dumps({'loaded':True,'speaker':CONFIG['speaker'],'mode':CONFIG.get('mode','custom_voice')}),flush=True)
    metrics=[]
    for label in labels:
        instruction=STYLES[label] if CONFIG.get('mode')!='speaker_reference' else None
        engine.config['style']=label
        started=time.perf_counter();chunks=[];rate=48000
        generated=engine.executor.submit(engine.generate,args.text,chunks.append,lambda:False).result()
        elapsed=time.perf_counter()-started
        audio=np.concatenate(chunks)
        if not np.isfinite(audio).all() or not audio.size:raise ValueError('Invalid generated audio')
        output=ROOT/f'artifacts/tts-{label}.wav'
        sf.write(output,audio,rate)
        rms=float(np.sqrt(np.mean(audio**2)))
        gain=min(0.065/max(rms,1e-8),0.95/max(float(np.max(np.abs(audio))),1e-8))
        sf.write(ROOT/f'artifacts/preview-{label}.wav',audio*gain,rate)
        row={'style':label,'model':MODEL,'revision':REVISION,'speaker':CONFIG['speaker'],
             'text':args.text,'instruction':instruction,'seconds':len(audio)/rate,
             'mode':CONFIG.get('mode','custom_voice'),
             'referenceAudio':CONFIG.get('referenceAudio'),'referenceSha256':CONFIG.get('referenceSha256'),
             'firstChunkMs':generated['firstChunkMs'],'totalSeconds':round(elapsed,2),
             'realTimeFactor':round(elapsed/(len(audio)/rate),3),
             'peak':float(np.max(np.abs(audio))),'output':str(output)}
        metrics.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
    (ROOT/('artifacts/tts-comparison-'+ '-'.join(labels)+'.json')).write_text(json.dumps(metrics,ensure_ascii=False,indent=2))
    engine.executor.shutdown(wait=True)


if __name__=='__main__':main()
