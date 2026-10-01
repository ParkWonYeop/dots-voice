"""Preview alternative female voices without changing the active dot call."""
import argparse
import concurrent.futures
import gc
import json
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
import soundfile as sf
from huggingface_hub import snapshot_download
from mlx_audio.tts.utils import load_model

ROOT=Path(__file__).resolve().parents[1]


def run(config,selected,download):
    # Keep MLX loading and generation on one worker and its own streams.
    streams=[mx.new_stream(mx.cpu),mx.new_stream(mx.gpu)]
    for stream in streams:mx.set_default_stream(stream)
    rows=[]
    for key,model_config in config['models'].items():
        voices=[v for v in selected if v['model']==key]
        if not voices:continue
        directory=ROOT/model_config['directory']
        if download:
            snapshot_download(model_config['repo'],revision=model_config['revision'],local_dir=directory)
        model=load_model(directory)
        method=model.generate_custom_voice if model_config['mode']=='custom_voice' else model.generate_voice_design
        for index,voice in enumerate(voices):
            kwargs={'language':config['language'],'instruct':voice['instruct'],
                    'temperature':config['temperature'],'max_tokens':512,
                    'stream':True,'streaming_interval':config['streamingInterval']}
            if 'speaker' in voice:kwargs['speaker']=voice['speaker']
            if index==0:
                for result in method(text='안녕!',**kwargs):mx.eval(result.audio)
            mx.random.seed(config['seed']);started=time.perf_counter();first=None;chunks=[]
            for result in method(text=config['text'],**kwargs):
                pcm=np.asarray(result.audio,dtype=np.float32)
                if not pcm.size or not np.isfinite(pcm).all():raise ValueError('Invalid voice output')
                if first is None:first=(time.perf_counter()-started)*1000
                chunks.append(pcm);rate=result.sample_rate
            elapsed=time.perf_counter()-started
            if not chunks:raise ValueError('No audio generated')
            audio=np.concatenate(chunks);name=voice['id']
            sf.write(ROOT/f'artifacts/voice-{name}.wav',audio,rate)
            rms=float(np.sqrt(np.mean(audio**2)));peak=float(np.abs(audio).max())
            gain=min(0.065/max(rms,1e-8),0.95/max(peak,1e-8))
            preview=ROOT/f'artifacts/preview-voice-{name}.wav'
            sf.write(preview,audio*gain,rate)
            row={'id':name,'label':voice['label'],'model':model_config,'speaker':voice.get('speaker'),
                 'instruct':voice['instruct'],'text':config['text'],'seconds':len(audio)/rate,
                 'firstChunkMs':round(first,1),'generationSeconds':round(elapsed,2),
                 'realTimeFactor':round(elapsed/(len(audio)/rate),3),'peak':peak,'preview':str(preview)}
            rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
        del result,model,method;gc.collect();mx.clear_cache()
    (ROOT/'artifacts/voice-candidates.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--voices',help='Comma-separated candidate ids')
    parser.add_argument('--skip-download',action='store_true');args=parser.parse_args()
    config=json.loads((ROOT/'config/voice_candidates.json').read_text())
    ids=args.voices.split(',') if args.voices else [v['id'] for v in config['voices']]
    selected=[v for v in config['voices'] if v['id'] in ids]
    if set(ids)-{v['id'] for v in selected}:parser.error('Unknown voice id')
    (ROOT/'artifacts').mkdir(exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(run,config,selected,not args.skip_download).result()


if __name__=='__main__':main()
