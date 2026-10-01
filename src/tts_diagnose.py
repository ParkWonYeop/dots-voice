"""Measure the selected Windows voice locally; no microphone or account is used."""
import json
from pathlib import Path
import time
import numpy as np
import soundfile as sf
from tts_torch_engine import TorchEngine

ROOT = Path(__file__).resolve().parents[1]


def main():
    config = json.loads((ROOT / 'config/voice_settings.json').read_bytes())
    engine = TorchEngine(config)
    started = time.perf_counter()
    result = {'ok': False, 'device': config['device'], 'model': config['model'],
              'referenceSha256': config['referenceSha256']}
    try:
        engine.initialize()
        result['loadSeconds'] = round(time.perf_counter() - started, 2)
        engine.generate('안녕!', lambda pcm: None, lambda: False)
        audio = []
        metrics = engine.generate('오늘은 어떤 얘기를 해볼까?', audio.append, lambda: False)
        if not audio or not metrics['generatedSeconds']:
            raise RuntimeError('No generated audio')
        (ROOT / 'artifacts').mkdir(exist_ok=True)
        sf.write(ROOT / 'artifacts/windows-voice-test.wav', np.concatenate(audio), 48000)
        result.update(ok=True, **metrics)
        result['realTimeFactor'] = round(metrics['generationMs'] / 1000 / metrics['generatedSeconds'], 3)
    except Exception as error:
        result.update(error=f'{type(error).__name__}: {error}',
                      cudaOutOfMemory='out of memory' in str(error).lower() and config['device'].startswith('cuda'))
    finally:
        engine.shutdown()
        (ROOT / 'runtime').mkdir(exist_ok=True)
        (ROOT / 'runtime/benchmark.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
