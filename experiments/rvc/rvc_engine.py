"""Local RVC v1/v2 inference. User model is read with weights_only=True."""
from pathlib import Path
import json
import sys
import time
import numpy as np
import torch
import torch.nn.functional as F
import pyworld
from scipy.signal import resample_poly
from transformers import HubertConfig, HubertModel

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'runtime/vendor'))
from infer_pack.models import SynthesizerTrnMs768NSFsid, SynthesizerTrnMs256NSFsid


class RVC:
    def __init__(self, model_path, device='mps', pitch_shift=6, speaker=0):
        torch.set_num_threads(4)
        self.device = torch.device(device)
        self.pitch_shift = pitch_shift
        self.speaker = speaker
        checkpoint = torch.load(model_path, map_location='cpu', weights_only=True)
        self.version = checkpoint.get('version', 'v1')
        self.sample_rate = int(checkpoint['config'][-1])
        if not checkpoint.get('f0', 1):
            raise ValueError('This test engine requires a pitch-conditioned RVC model')
        cls = SynthesizerTrnMs768NSFsid if self.version == 'v2' else SynthesizerTrnMs256NSFsid
        self.generator = cls(*checkpoint['config'], is_half=False)
        del self.generator.enc_q
        loaded = self.generator.load_state_dict(checkpoint['weight'], strict=False)
        if loaded.missing_keys or loaded.unexpected_keys:
            raise ValueError(f'Unexpected generator weights: {loaded}')
        self.generator.eval().to(self.device)
        config = HubertConfig.from_dict(json.loads((ROOT/'runtime/vendor/contentvec-config.json').read_text()))
        config.apply_spec_augment = False
        self.encoder = HubertModel(config)
        weights = torch.load(ROOT/'models/contentvec.bin', map_location='cpu', weights_only=True)
        projection = {k: weights.pop(k) for k in ('final_proj.weight','final_proj.bias')}
        for prefix in ('encoder.pos_conv_embed.conv',):
            for old, new in [('weight_g','parametrizations.weight.original0'), ('weight_v','parametrizations.weight.original1')]:
                key = f'{prefix}.{old}'
                if key in weights and f'{prefix}.{new}' in self.encoder.state_dict():
                    weights[f'{prefix}.{new}'] = weights.pop(key)
        self.encoder.load_state_dict(weights, strict=True)
        self.encoder.eval().to(self.device)
        self.projection = {k.split('.')[1]:v.to(self.device) for k,v in projection.items()}
        self.info = {'model':Path(model_path).name, 'version':self.version, 'sampleRate':self.sample_rate,
                     'device':device, 'pitchShift':pitch_shift, 'speaker':speaker, 'indexRate':0}

    @torch.inference_mode()
    def convert(self, audio, input_rate=48000):
        started = time.perf_counter()
        x = np.asarray(audio, dtype=np.float32)
        x16 = resample_poly(x, 16000, input_rate).astype(np.float32)
        # WORLD frames use 10 ms, matching RVC's doubled HuBERT feature sequence.
        f0, times = pyworld.dio(x16.astype(np.float64), 16000, f0_floor=50, f0_ceil=1100, frame_period=10)
        f0 = pyworld.stonemask(x16.astype(np.float64), f0, times, 16000)
        f0 *= 2**(self.pitch_shift/12)
        source = torch.from_numpy(x16[None]).to(self.device)
        result = self.encoder(source, output_hidden_states=self.version!='v2')
        features = result.last_hidden_state if self.version=='v2' else F.linear(result.hidden_states[9], **self.projection)
        features = F.interpolate(features.transpose(1,2), scale_factor=2).transpose(1,2)
        frames = min(features.shape[1], len(f0), len(x16)//160)
        features = features[:, :frames]
        f0 = f0[:frames].astype(np.float32)
        mel = 1127*np.log1p(f0/700)
        low, high = 1127*np.log1p(50/700), 1127*np.log1p(1100/700)
        positive = mel > 0
        mel[positive] = (mel[positive]-low)*254/(high-low)+1
        pitch = np.clip(np.rint(mel),1,255).astype(np.int64)
        waveform = self.generator.infer(features, torch.tensor([frames],device=self.device),
            torch.from_numpy(pitch[None]).to(self.device), torch.from_numpy(f0[None]).to(self.device),
            torch.tensor([self.speaker],device=self.device))[0][0,0].float().cpu().numpy()
        waveform = np.clip(waveform,-1,1)
        out = resample_poly(waveform, input_rate, self.sample_rate).astype(np.float32)
        out = np.pad(out, (0,max(0,len(x)-len(out))))[:len(x)]
        return out, (time.perf_counter()-started)*1000


if __name__ == '__main__':
    import argparse
    import soundfile as sf
    parser = argparse.ArgumentParser()
    parser.add_argument('--model',required=True)
    parser.add_argument('--device',default='mps')
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--pitch',type=int,default=6)
    args = parser.parse_args()
    engine = RVC(args.model,args.device,args.pitch)
    audio,rate = sf.read(args.input,dtype='float32')
    if audio.ndim==2: audio=audio.mean(axis=1)
    out,ms = engine.convert(audio,rate)
    sf.write(args.output,out,rate)
    print(json.dumps({**engine.info,'inputSeconds':len(audio)/rate,'inferenceMs':round(ms,1),
                     'outputRms':float(np.sqrt(np.mean(out*out)))},ensure_ascii=False))
