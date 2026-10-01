"""Continuous PCM resampling without resetting the filter at TTS chunk edges."""
from fractions import Fraction
import av
import numpy as np


class PcmResampler:
    def __init__(self,rate=48000):
        self.resampler=av.AudioResampler(format='fltp',layout='mono',rate=rate)
        self.samples=0

    def push(self,pcm,rate):
        frame=av.AudioFrame.from_ndarray(np.ascontiguousarray(pcm,dtype=np.float32)[None],
                                       format='fltp',layout='mono')
        frame.sample_rate=rate;frame.time_base=Fraction(1,rate);frame.pts=self.samples
        self.samples+=len(pcm)
        return self._samples(self.resampler.resample(frame))

    def finish(self):return self._samples(self.resampler.resample(None))

    @staticmethod
    def _samples(frames):
        return [frame.to_ndarray().reshape(-1).astype(np.float32) for frame in frames]


class PauseLimiter:
    """Shorten only sustained near-silence; preserve speech and short closures."""
    def __init__(self,max_pause=0.24,threshold=0.002,rate=48000):
        self.frame_size=round(rate*0.01);self.limit=round(max_pause*rate)
        self.threshold=threshold;self.pending=np.empty(0,dtype=np.float32)
        self.silent_samples=0;self.removed_samples=0

    def push(self,pcm,final=False,max_remove_samples=None):
        pcm=np.concatenate((self.pending,pcm));end=len(pcm) if final else len(pcm)//self.frame_size*self.frame_size
        self.pending=pcm[end:];kept=[]
        for start in range(0,end,self.frame_size):
            frame=pcm[start:min(start+self.frame_size,end)]
            if np.sqrt(np.mean(frame*frame))<self.threshold:
                keep=min(len(frame),max(0,self.limit-self.silent_samples))
                remove=len(frame)-keep
                if max_remove_samples is not None:
                    remove=min(remove,max_remove_samples);max_remove_samples-=remove
                    keep=len(frame)-remove
                self.silent_samples+=len(frame);self.removed_samples+=len(frame)-keep
                if keep:kept.append(frame[:keep])
            else:
                self.silent_samples=0;kept.append(frame)
        return np.concatenate(kept) if kept else np.empty(0,dtype=np.float32)
