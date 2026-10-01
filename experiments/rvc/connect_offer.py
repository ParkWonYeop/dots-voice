"""Exchange a locally downloaded loopback offer for an answer script."""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from aiohttp import ClientSession

ROOT=Path(__file__).resolve().parent
async def main():
    parser=argparse.ArgumentParser();parser.add_argument('offer')
    parser.add_argument('--tts',action='store_true');args=parser.parse_args()
    config=json.loads((ROOT/('runtime/tts-bridge-config.json' if args.tts else 'runtime/bridge-config.json')).read_text())
    address=urlparse(config['url'])
    token=parse_qs(address.query)['token'][0]
    offer=json.loads(Path(args.offer).expanduser().read_text())
    async with ClientSession()as session:
        async with session.post(f'http://127.0.0.1:{address.port}/offer',json=offer,headers={'Authorization':'Bearer '+token})as response:
            response.raise_for_status();answer=await response.json()
    output=ROOT/'runtime/install-answer.js'
    api='__dotsTts' if args.tts else '__dotsRtc'
    output.write_text(api+'.setAnswer('+json.dumps(answer)+').then(()=>console.log("DOTS_ANSWER_APPLIED",JSON.stringify('+api+'.status()))).catch(error=>console.error("DOTS_ANSWER_ERROR",error));\n')
    print(output)
if __name__=='__main__':asyncio.run(main())
