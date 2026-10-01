"""Prepare the pinned TTS environment and a locally loaded Chrome extension."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
from voice_launcher import ROOT, RUNTIME, HOST, extension_id


def run(*args):
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def prepare_environment():
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise RuntimeError('이 실행기는 Apple Silicon Mac용입니다.')
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError('Python 3.11로 실행하세요.')
    python = ROOT / '.tts-venv/bin/python'
    if not python.exists():
        print('음성 실행 환경을 만듭니다.', flush=True)
        run(sys.executable, '-m', 'venv', ROOT / '.tts-venv')
    # Check distribution metadata without importing MLX or loading another model.
    check = """
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import sys
try:
    for line in Path('requirements/requirements.tts.lock.txt').read_text().splitlines():
        if line.strip() and not line.startswith('#'):
            name, expected = line.split('==')
            if version(name) != expected: sys.exit(1)
except PackageNotFoundError: sys.exit(1)
"""
    if subprocess.run([str(python), '-c', check], cwd=ROOT).returncode:
        print('고정 버전 의존성을 설치합니다.', flush=True)
        run(python, '-m', 'pip', 'install', '-r', ROOT / 'requirements/requirements.tts.lock.txt')
    config = json.loads((ROOT / 'config/voice_settings.json').read_text())
    reference = ROOT / config['referenceAudio']
    if hashlib.sha256(reference.read_bytes()).hexdigest() != config['referenceSha256']:
        raise RuntimeError('참조 음성 파일이 변경됐습니다.')
    print('모델 파일을 확인합니다. 처음 설치할 때만 다운로드가 오래 걸립니다.', flush=True)
    # Download only; do not run the comparison script or contend with an active call.
    run(python, '-c', "from huggingface_hub import snapshot_download; import json; from pathlib import Path; c=json.loads(Path('config/voice_settings.json').read_text()); snapshot_download(c['model'], revision=c['revision'], local_dir=c['modelDirectory'])")


def install_files():
    RUNTIME.mkdir(exist_ok=True)
    destination = RUNTIME / 'chrome-extension'
    destination.mkdir(exist_ok=True)
    for source in (ROOT / 'chrome-extension').iterdir():
        if source.is_file():
            shutil.copy2(source, destination / source.name)
    # Chrome must be able to start the host before Python can report failures.
    # Keep the bootstrap and its stderr log in the normal application-data folder,
    # independently of the project's location (e.g. a protected Documents folder).
    host_dir = Path.home() / 'Library/Application Support/Dots Voice'
    host_dir.mkdir(parents=True, exist_ok=True)
    host_dir.chmod(0o700)
    error_log = host_dir / 'native-host.log'
    error_log.touch(mode=0o600, exist_ok=True)
    error_log.chmod(0o600)
    wrapper = host_dir / 'chrome-voice-host'
    wrapper.write_text('#!/bin/sh\numask 077\nexec 2>>' + shlex.quote(str(error_log)) +
                       '\nprintf "Starting Dots Voice native host\\n" >&2\nexec ' +
                       shlex.quote(str(ROOT / '.tts-venv/bin/python')) +
                       ' -X utf8 -u ' + shlex.quote(str(ROOT / 'src/voice_launcher.py')) + ' "$@"\n',
                       encoding='utf-8')
    wrapper.chmod(0o700)
    manifest_dir = Path.home() / 'Library/Application Support/Google/Chrome/NativeMessagingHosts'
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = {'name': HOST, 'description': 'Dots local voice bridge', 'path': str(wrapper),
                'type': 'stdio', 'allowed_origins': [f'chrome-extension://{extension_id()}/']}
    path = manifest_dir / (HOST + '.json')
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    path.chmod(0o600)
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    prepare_environment()
    destination = install_files()
    print(f'\n설치 파일 준비 완료: {destination}\n'
          'Chrome 확장 프로그램 → 개발자 모드 → 압축해제된 확장 프로그램 로드에서 위 폴더를 선택하세요.\n'
          '이미 등록했다면 Dots Voice 카드의 새로고침 버튼을 누르세요.\n'
          '이후 dots 탭에서 Dots Voice 버튼 한 번 → 연결 완료 후 통화 시작.\n'
          '서버는 자동 실행되며 터미널 창을 닫아도 유지됩니다.', flush=True)
    if not args.no_open:
        run('/usr/bin/open', str(destination))
        run('/usr/bin/open', '-a', 'Google Chrome', 'chrome://extensions')


if __name__ == '__main__':
    main()
