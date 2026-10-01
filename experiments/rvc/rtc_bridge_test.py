"""Regression for an interruption during an RTP frame's pacing wait."""
import asyncio
import time
import numpy as np
from rtc_bridge import ConvertedTrack


class IdleSource:
    async def recv(self):
        await asyncio.Future()


async def main():
    track=ConvertedTrack(IdleSource(),None,{},False)
    track.worker.cancel()
    track.output=np.ones(1920,dtype=np.float32)*0.1
    track.started=time.monotonic()
    track.pts=4800  # 100 ms playback deadline
    pending=asyncio.create_task(track.recv())
    await asyncio.sleep(0.02)
    track.flush()
    frame=await asyncio.wait_for(pending,1)
    assert frame.samples==960, 'An interruption must not emit an empty RTP frame'
    assert not frame.to_ndarray().any(), 'Interrupted audio must become silence'
    await track.queue.put(np.ones(15360,dtype=np.float32)*0.2)
    resumed=await asyncio.wait_for(track.recv(),1)
    assert resumed.samples==960 and resumed.to_ndarray().any()
    track.stop()
    print('interruption pacing regression passed')


if __name__=='__main__':asyncio.run(main())
