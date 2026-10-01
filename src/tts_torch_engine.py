"""Official Qwen3-TTS PyTorch backend: complete phrase synthesis, then RTC PCM."""
import concurrent.futures
import hashlib
from pathlib import Path
import time

import numpy as np
import soundfile as sf
from audio_stream import PcmResampler, PauseLimiter

ROOT = Path(__file__).resolve().parents[1]


class GenerationCancelled(Exception):
    pass


class TorchEngine:
    def __init__(self, config):
        self.config = config
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix='dots-torch')

    def initialize(self):
        import torch
        from qwen_tts import Qwen3TTSModel
        self.torch = torch
        self.device = self.config.get('device', 'cpu')
        if self.device.startswith('cuda') and not torch.cuda.is_available():
            raise RuntimeError('CUDA를 사용할 수 없습니다. install-windows.cmd를 다시 실행하세요.')
        torch.set_num_threads(self.config.get('cpuThreads', 4))
        dtype = getattr(torch, self.config.get('dtype', 'float32'))
        self.model = Qwen3TTSModel.from_pretrained(
            str(ROOT / self.config['modelDirectory']), device_map=self.device,
            dtype=dtype, attn_implementation='sdpa', local_files_only=True)
        reference = ROOT / self.config['referenceAudio']
        if hashlib.sha256(reference.read_bytes()).hexdigest() != self.config['referenceSha256']:
            raise ValueError('Selected voice reference has changed')
        pcm, rate = sf.read(reference, dtype='float32')
        if rate != 24000 or pcm.ndim != 1 or not np.isfinite(pcm).all():
            raise ValueError('Invalid selected voice reference')
        self.prompt = self.model.create_voice_clone_prompt(ref_audio=(pcm, rate), x_vector_only_mode=True)

    def generate(self, text, emit, cancelled):
        if cancelled():
            return None
        started = time.perf_counter()
        self.torch.manual_seed(self.config['seed'])
        # qwen-tts 0.1.1 drops arbitrary stopping_criteria before talker.generate.
        # Check at each talker forward instead; do not wait for an obsolete phrase.
        def check_cancel(module, args):
            if cancelled():
                raise GenerationCancelled()
        hook = self.model.model.talker.register_forward_pre_hook(check_cancel)
        try:
            waves, rate = self.model.generate_voice_clone(
                text=text, language=self.config['language'], voice_clone_prompt=self.prompt,
                non_streaming_mode=False, temperature=self.config['temperature'],
                repetition_penalty=self.config['repetitionPenalty'], max_new_tokens=1024)
        except GenerationCancelled:
            return None
        finally:
            hook.remove()
        if cancelled():
            return None
        pcm = np.asarray(waves[0], dtype=np.float32)
        if pcm.ndim != 1 or not len(pcm) or not np.isfinite(pcm).all():
            raise ValueError('Invalid TTS output')
        resampler = PcmResampler()
        pieces = resampler.push(pcm, rate) + resampler.finish()
        pcm = np.concatenate(pieces)
        raw_seconds = len(pcm) / 48000
        if self.config.get('maxPauseSeconds'):
            limiter = PauseLimiter(self.config['maxPauseSeconds'], self.config.get('silenceThreshold', .002))
            pcm = limiter.push(pcm, final=True)
        first_ms = (time.perf_counter() - started) * 1000
        # This splits already synthesized audio for transport; it is not streaming inference.
        for start in range(0, len(pcm), 15360):
            if cancelled():
                return None
            emit(pcm[start:start + 15360])
        seconds = len(pcm) / 48000
        return {'firstChunkMs': round(first_ms, 1), 'generatedSeconds': seconds,
                'rawGeneratedSeconds': raw_seconds, 'removedSilenceSeconds': round(raw_seconds - seconds, 3),
                'generationMs': round((time.perf_counter() - started) * 1000, 1),
                'device': self.device, 'synthesisMode': 'phrase'}

    def shutdown(self):
        self.executor.shutdown(wait=True, cancel_futures=True)
