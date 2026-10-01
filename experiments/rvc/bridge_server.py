"""Loopback-only bridge for decoded incoming dot speech; no microphone capture."""
import argparse
import asyncio
import json
import secrets
import struct
import time
from pathlib import Path
import numpy as np
from aiohttp import web, WSMsgType
from rvc_engine import RVC

ROOT = Path(__file__).resolve().parent


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model',required=True)
    parser.add_argument('--device',default='mps')
    parser.add_argument('--pitch',type=int,default=6)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--record-test',action='store_true')
    args = parser.parse_args()
    engine = RVC(args.model,args.device,args.pitch)
    warm = np.zeros(48000,dtype=np.float32)
    for _ in range(3): engine.convert(warm)
    token = secrets.token_urlsafe(24)
    config = {'url':f'ws://127.0.0.1:{args.port}/voice?token={token}', 'model':engine.info}
    (ROOT/'runtime/bridge-config.json').write_text(json.dumps(config))
    stats = {'model':engine.info,'connections':0,'blocks':0,'inferenceMs':[], 'inputPeak':0.,'outputPeak':0.}
    lock = asyncio.Lock()
    rtc_peers=set()

    async def health(request):
        return web.json_response({**stats,'inferenceMs':stats['inferenceMs'][-20:]})

    async def websocket(request):
        origin = request.headers.get('Origin','')
        if request.query.get('token')!=token or origin not in ('https://chatgpt.com',f'http://127.0.0.1:{args.port}',''):
            raise web.HTTPForbidden()
        ws = web.WebSocketResponse(max_msg_size=1_000_000,heartbeat=20)
        await ws.prepare(request)
        stats['connections']+=1
        sample_rate=48000
        pending=np.empty(0,dtype=np.float32)
        history=np.zeros(30720,dtype=np.float32)
        epoch=0
        input_record=[]; output_record=[]
        await ws.send_json({'type':'ready',**engine.info,'blockMs':320,'lookaheadMs':40})
        try:
            async for msg in ws:
                if msg.type==WSMsgType.TEXT:
                    command=json.loads(msg.data)
                    if command.get('type')=='config':
                        sample_rate=int(command['sampleRate'])
                        if sample_rate!=48000: raise ValueError('Use AudioContext sampleRate 48000')
                    elif command.get('type')=='flush':
                        epoch=int(command['epoch']); pending=np.empty(0,dtype=np.float32);history.fill(0)
                    continue
                if msg.type!=WSMsgType.BINARY: continue
                packet=msg.data
                if len(packet)<8 or (len(packet)-4)%4: raise ValueError('Malformed PCM packet')
                packet_epoch=struct.unpack('<I',packet[:4])[0]
                if packet_epoch!=epoch: continue
                samples=np.frombuffer(packet[4:],dtype='<f4').copy()
                if not np.isfinite(samples).all():raise ValueError('Non-finite input audio')
                pending=np.concatenate((pending,samples))
                if pending.size>48000*2:raise ValueError('Conversion cannot keep up with input')
                block=15360; ahead=1920
                while pending.size>=block+ahead:
                    source=np.concatenate((history,pending[:block+ahead]))
                    input_chunk=pending[:block].copy()
                    # Silence doesn't need neural inference and must remain silent.
                    if np.sqrt(np.mean(source*source))<0.0001:
                        converted=np.zeros_like(source); elapsed=0.
                    else:
                        async with lock:
                            converted,elapsed=await asyncio.to_thread(engine.convert,source,sample_rate)
                    output=converted[len(history):len(history)+block].copy()
                    history=np.concatenate((history,input_chunk))[-len(history):]
                    pending=pending[block:]
                    stats['blocks']+=1
                    stats['inferenceMs'].append(round(elapsed,2))
                    stats['inferenceMs']=stats['inferenceMs'][-200:]
                    stats['inputPeak']=max(stats['inputPeak'],float(np.max(np.abs(input_chunk))))
                    stats['outputPeak']=max(stats['outputPeak'],float(np.max(np.abs(output))))
                    if args.record_test:
                        input_record.append(input_chunk); output_record.append(output)
                    await ws.send_bytes(struct.pack('<I',epoch)+output.astype('<f4').tobytes())
                    await ws.send_json({'type':'metrics','inferenceMs':round(elapsed,2),'blocks':stats['blocks'],
                        'inputRms':float(np.sqrt(np.mean(input_chunk**2))),'outputRms':float(np.sqrt(np.mean(output**2)))})
        except Exception as error:
            await ws.send_json({'type':'error','message':str(error)})
        finally:
            if input_record:
                import soundfile as sf
                stamp=int(time.time())
                sf.write(ROOT/f'artifacts/dot-input-{stamp}.wav',np.concatenate(input_record),sample_rate)
                sf.write(ROOT/f'artifacts/dot-yui-{stamp}.wav',np.concatenate(output_record),sample_rate)
            (ROOT/'artifacts/bridge-stats.json').write_text(json.dumps(stats,indent=2))
            await ws.close()
        return ws

    async def rtc_offer(request):
        if request.headers.get('Authorization') != f'Bearer {token}':raise web.HTTPForbidden()
        from rtc_bridge import accept_offer
        answer=await accept_offer(await request.json(),engine,stats,args.record_test,rtc_peers)
        return web.json_response(answer)

    app=web.Application()
    app.router.add_get('/health',health)
    app.router.add_get('/voice',websocket)
    app.router.add_post('/offer',rtc_offer)
    runner=web.AppRunner(app);await runner.setup()
    await web.TCPSite(runner,'127.0.0.1',args.port).start()
    print(json.dumps({'ready':True,'listen':f'127.0.0.1:{args.port}','model':engine.info}),flush=True)
    try:await asyncio.Event().wait()
    finally:
        await asyncio.gather(*(pc.close() for pc in rtc_peers),return_exceptions=True)
        await runner.cleanup()


if __name__=='__main__': asyncio.run(main())
