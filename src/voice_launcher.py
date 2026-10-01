"""Chrome native messaging and idempotent management of the local TTS server."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import build_opener, ProxyHandler, Request

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'runtime'
HOST = 'com.dots.local_voice'
BASE = 'http://127.0.0.1:8766'
SERVICE = 'dots-local-tts-v1'
HTTP = build_opener(ProxyHandler({}))
MAX_MESSAGE = 128 * 1024
WINDOWS = sys.platform == 'win32'


def environment_python():
    return ROOT / ('.tts-venv/Scripts/python.exe' if WINDOWS else '.tts-venv/bin/python')


def lock_start(stream):
    if WINDOWS:
        import msvcrt
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            import errno
            if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise BlockingIOError() from error
            raise
    else:
        import fcntl
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)


def extension_id():
    manifest = json.loads((ROOT / 'chrome-extension/manifest.json').read_text())
    digest = hashlib.sha256(base64.b64decode(manifest['key'])).hexdigest()[:32]
    return ''.join(chr(ord('a') + int(c, 16)) for c in digest)


def config_digest():
    return hashlib.sha256((ROOT / 'config/voice_settings.json').read_bytes()).hexdigest()


def root_id():
    return hashlib.sha256(str(ROOT).encode()).hexdigest()


def health():
    try:
        with HTTP.open(BASE + '/health', timeout=2) as response:
            return json.load(response)
    except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
        return None


def validate_server(status, check_config=True):
    if status.get('service') != SERVICE or status.get('rootId') != root_id():
        raise RuntimeError('8766 포트에 다른 서버 또는 이전 버전이 있습니다. 기존 서버를 종료한 뒤 다시 실행하세요.')
    if check_config and status.get('configDigest') != config_digest():
        raise RuntimeError('목소리 설정이 변경됐습니다. 종료 실행 파일을 실행한 뒤 다시 연결하세요.')
    if check_config and status.get('error'):
        raise RuntimeError('음성 서버 오류가 있습니다. 종료 후 다시 연결하세요.')


def ensure_server(timeout=None):
    if timeout is None:
        config = json.loads((ROOT / 'config/voice_settings.json').read_bytes())
        timeout = min(600, max(30, config.get('startupTimeoutSeconds', 120)))
    RUNTIME.mkdir(exist_ok=True)
    # Serialize starts across popup retries, tabs, and separate Chrome windows.
    with (RUNTIME / 'tts-start.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'\0'); lock.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                lock_start(lock)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('다른 실행기의 서버 시작이 끝나지 않았습니다.')
                time.sleep(.2)
        status = health()
        if status is not None:
            validate_server(status)
            return {'reused': True, 'speaker': status['speaker'], 'mode': status['mode']}
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(('127.0.0.1', 8766))
            except OSError:
                raise RuntimeError('8766 포트가 사용 중입니다. 기존 서버 상태를 확인하세요.') from None
        python = environment_python()
        if not python.exists():
            raise RuntimeError('패키지의 설치 실행 파일을 먼저 실행하세요.')
        log_path = RUNTIME / 'tts-server.log'
        fd = os.open(log_path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
        os.chmod(log_path, 0o600)
        with os.fdopen(fd, 'ab', buffering=0) as log:
            options = {'creationflags': subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {'start_new_session': True}
            process = subprocess.Popen([str(python), '-X', 'utf8', '-u', str(ROOT / 'src/tts_bridge_server.py')],
                                       cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       close_fds=True, **options)
        while time.monotonic() < deadline:
            status = health()
            if status is not None:
                validate_server(status)
                return {'reused': False, 'speaker': status['speaker'], 'mode': status['mode']}
            if process.poll() is not None:
                raise RuntimeError('음성 서버 시작 실패. runtime/tts-server.log를 확인하세요.')
            time.sleep(.25)
        # Only terminate the process group we just created, never an arbitrary port owner.
        if process.poll() is None:
            if WINDOWS:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                import signal
                os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=10)
        raise RuntimeError('음성 서버 시작 시간 초과. runtime/tts-server.log를 확인하세요.')


def authenticated_post(path, body):
    config = json.loads((RUNTIME / 'tts-bridge-config.json').read_text())
    address = urlparse(config['url'])
    if address.scheme != 'http' or address.hostname != '127.0.0.1' or address.port != 8766:
        raise RuntimeError('잘못된 로컬 음성 서버 주소입니다.')
    token = parse_qs(address.query)['token'][0]
    request = Request(BASE + path, data=json.dumps(body).encode(),
                      headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
    try:
        with HTTP.open(request, timeout=20) as response:
            return json.load(response)
    except URLError:
        raise RuntimeError('로컬 음성 서버 연결에 실패했습니다. 다시 연결하세요.') from None


def handle(message):
    command = message.get('type')
    if command == 'ping':
        # A setup probe must not start the model or depend on GPU availability.
        return {'service': SERVICE, 'protocol': 1}
    if command == 'start':
        return ensure_server()
    if command == 'offer':
        offer = message.get('offer')
        if not isinstance(offer, dict) or offer.get('type') != 'offer':
            raise ValueError('Invalid offer')
        sdp = offer.get('sdp')
        if not isinstance(sdp, str) or not sdp.startswith('v=0') or len(sdp) > 100_000:
            raise ValueError('Invalid SDP')
        status = health()
        if status is None:
            raise RuntimeError('음성 서버가 중지됐습니다. 다시 연결하세요.')
        validate_server(status)
        return authenticated_post('/offer', {'type': 'offer', 'sdp': sdp})
    raise ValueError('Unknown command')


def read_exact(stream, size):
    chunks = bytearray()
    while len(chunks) < size:
        chunk = stream.read(size - len(chunks))
        if not chunk:
            raise EOFError('Truncated native message')
        chunks.extend(chunk)
    return bytes(chunks)


def read_message(stream):
    first = stream.read(1)
    if not first:
        return None
    length = struct.unpack('=I', first + read_exact(stream, 3))[0]
    if not 0 < length <= MAX_MESSAGE:
        raise ValueError('Invalid native message size')
    message = json.loads(read_exact(stream, length))
    if not isinstance(message, dict):
        raise ValueError('Invalid native message')
    return message


def native_main(origin):
    if origin != f'chrome-extension://{extension_id()}/':
        raise ValueError('Unauthorized extension')
    if WINDOWS:
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    while (message := read_message(sys.stdin.buffer)) is not None:
        try:
            result = {'id': message.get('id'), 'ok': True, 'result': handle(message)}
        except Exception as error:
            result = {'id': message.get('id'), 'ok': False, 'error': str(error)}
        data = json.dumps(result, ensure_ascii=False).encode()
        sys.stdout.buffer.write(struct.pack('=I', len(data)) + data)
        sys.stdout.buffer.flush()


def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith('chrome-extension://'):
        native_main(sys.argv[1])
        return
    parser = argparse.ArgumentParser()
    parser.add_argument('--stop', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.stop:
        status = health()
        if status is None:
            print('실행 중인 음성 서버가 없습니다.')
            return
        validate_server(status, check_config=False)
        authenticated_post('/shutdown', {})
        print('음성 서버를 종료했습니다. 연결된 탭은 원래 목소리로 돌아갑니다.')
    elif args.status:
        status = health()
        print(json.dumps({k: status.get(k) for k in ('service', 'mode', 'speaker', 'connection', 'error')} if status else {'running': False}, ensure_ascii=False))
    else:
        print(json.dumps(ensure_server(), ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
