"""Windows 11 x64 installer with hardware selection and a measured voice test."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys

from hardware_profile import inspect_hardware, choose_profile
from voice_launcher import ROOT, RUNTIME, HOST, SERVICE, MAX_MESSAGE, extension_id, health, validate_server


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True, **kwargs)


def install_files():
    import winreg
    RUNTIME.mkdir(exist_ok=True)
    destination = RUNTIME / 'chrome-extension'
    destination.mkdir(exist_ok=True)
    for source in (ROOT / 'chrome-extension').iterdir():
        if source.is_file():
            shutil.copy2(source, destination / source.name)
    # Relative paths are expanded by cmd.exe; keep Unicode paths out of the batch source.
    wrapper = RUNTIME / 'chrome-voice-host.cmd'
    wrapper.write_bytes(('@echo off\r\nsetlocal DisableDelayedExpansion\r\nset PYTHONUTF8=1\r\n'
                         '"%~dp0..\\.tts-venv\\Scripts\\python.exe" -X utf8 -u '
                         '"%~dp0..\\src\\voice_launcher.py" %* 2>>"%~dp0native-host.log"\r\n'
                         'exit /b %errorlevel%\r\n').encode('ascii'))
    manifest_path = RUNTIME / (HOST + '.json')
    save_json(manifest_path, {'name': HOST, 'description': 'Dots local voice bridge', 'path': str(wrapper),
                              'type': 'stdio', 'allowed_origins': [f'chrome-extension://{extension_id()}/']})
    # Per-user registration only. No administrator privileges or Chrome profile edits.
    # Chrome checks the 32-bit registry view first, even on 64-bit Windows.
    # Update both views so an earlier registration cannot shadow the current path.
    for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, 'Software\\Google\\Chrome\\NativeMessagingHosts\\' + HOST,
                                0, winreg.KEY_SET_VALUE | view) as key:
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(manifest_path))
    return destination


def check_native_host():
    """Run the registered cmd entry point and its binary pipes, without a model."""
    report = {'ok': False, 'scope': 'native-host-process', 'chromeVerified': False}
    try:
        manifest = json.loads((RUNTIME / (HOST + '.json')).read_bytes())
        wrapper = Path(manifest['path'])
        origin = f'chrome-extension://{extension_id()}/'
        if manifest['allowed_origins'] != [origin] or wrapper.name != 'chrome-voice-host.cmd':
            raise ValueError('Unexpected native host registration')
        data = json.dumps({'id': 'setup-check', 'type': 'ping'}).encode('utf-8')
        cmd = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'System32/cmd.exe'
        # Use the wrapper's working directory just as Chrome does. Avoid embedding
        # the Unicode project path in cmd's /c expression; keep stdout binary-only.
        command = subprocess.list2cmdline([str(cmd)]) + f' /d /s /c ""{wrapper.name}" "{origin}" --parent-window=0"'
        result = subprocess.run(command, cwd=wrapper.parent, input=struct.pack('=I', len(data)) + data,
                                capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        report['exitCode'] = result.returncode
        if result.stderr:
            report['stderr'] = result.stderr.decode('utf-8', errors='replace')[:4000]
        if result.returncode:
            raise RuntimeError('Native host exited before completing the probe')
        if len(result.stdout) < 4:
            raise ValueError('Native host returned no framed response')
        length = struct.unpack('=I', result.stdout[:4])[0]
        if not 0 < length <= MAX_MESSAGE or len(result.stdout) != length + 4:
            raise ValueError('Invalid native response length or extra stdout output')
        response = json.loads(result.stdout[4:])
        if response != {'id': 'setup-check', 'ok': True, 'result': {'service': SERVICE, 'protocol': 1}}:
            raise ValueError('Unexpected native host response')
        report['ok'] = True
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        report['error'] = f'{type(error).__name__}: {error}'
    save_json(RUNTIME / 'native-host-check.json', report)
    if not report['ok']:
        raise RuntimeError('Chrome 실행기 사전 검사 실패. runtime/native-host-check.json과 native-host.log를 확인하세요.')
    print('Chrome 실행기 프로세스·바이너리 통신 검사 통과. 실제 Chrome 연결은 확장 등록 후 확인하세요.', flush=True)


def prepare_environment(report, profile):
    python = ROOT / '.tts-venv/Scripts/python.exe'
    if not python.exists():
        run(sys.executable, '-m', 'venv', ROOT / '.tts-venv')
    run(python, '-m', 'pip', 'install', 'pip==26.0.1')
    index = 'https://download.pytorch.org/whl/' + profile['wheel']
    run(python, '-m', 'pip', 'install', 'torch==2.10.0+' + profile['wheel'],
        'torchaudio==2.10.0+' + profile['wheel'], '--index-url', index)
    run(python, '-m', 'pip', 'install', '--only-binary=:all:', '-r', ROOT / 'requirements/requirements.windows.txt')
    run(python, '-m', 'pip', 'check')
    try:
        tested = run(python, '-X', 'utf8', ROOT / 'src/hardware_profile.py', '--torch',
                     capture_output=True, text=True, encoding='utf-8', timeout=120)
    except subprocess.CalledProcessError as error:
        (RUNTIME / 'torch-probe.log').write_text((error.stdout or '') + (error.stderr or ''), encoding='utf-8')
        raise RuntimeError('PyTorch 장치 확인 실패. runtime/torch-probe.log를 확인하세요.') from error
    probe = json.loads(tested.stdout)
    profile.update(device=probe['device'], dtype=probe['dtype'])
    if probe['device'] == 'cpu':
        profile['reason'] = 'CPU 연산 확인 완료. 통화 지연은 음성 테스트 결과로 확인하세요.'
    else:
        profile['reason'] = 'CUDA 실제 연산 확인 완료.'
    report['torchProbe'] = probe
    report['selectedProfile'] = profile
    save_json(RUNTIME / 'hardware.json', report)
    config = json.loads((ROOT / 'config/voice_settings.windows.json').read_bytes())
    config.update({key: profile[key] for key in ('device', 'dtype', 'cpuThreads')})
    reference = ROOT / config['referenceAudio']
    if hashlib.sha256(reference.read_bytes()).hexdigest() != config['referenceSha256']:
        raise RuntimeError('선택한 목소리 참조 파일이 변경됐습니다.')
    save_json(ROOT / 'config/voice_settings.json', config)
    print(f"선택한 장치: {config['device']} / {config['dtype']}\n{profile['reason']}", flush=True)
    print('고정 revision의 모델을 내려받습니다. 첫 설치에는 수 GB의 다운로드가 필요합니다.', flush=True)
    run(python, '-X', 'utf8', '-c',
        "from huggingface_hub import snapshot_download; import json; from pathlib import Path; "
        "c=json.loads(Path('config/voice_settings.json').read_bytes()); "
        "snapshot_download(c['model'], revision=c['revision'], local_dir=c['modelDirectory'])")
    with (RUNTIME / 'installed-packages.txt').open('wb') as output:
        run(python, '-m', 'pip', 'freeze', stdout=output)
    return python, config


def benchmark(python, config, report):
    log_path = RUNTIME / 'setup-benchmark.log'
    result_path = RUNTIME / 'benchmark.json'
    result_path.unlink(missing_ok=True)
    def attempt():
        with log_path.open('ab') as output:
            try:
                run(python, '-X', 'utf8', '-u', ROOT / 'src/tts_diagnose.py', stdout=output,
                    stderr=subprocess.STDOUT, timeout=600)
            except subprocess.TimeoutExpired:
                save_json(result_path, {'ok': False, 'error': '음성 테스트가 10분 내 끝나지 않았습니다.'})
                return False
            except subprocess.CalledProcessError:
                return False
        return True
    print('짧은 음성 합성으로 실제 속도를 측정합니다. CPU에서는 오래 걸릴 수 있습니다.', flush=True)
    success = attempt()
    result = json.loads(result_path.read_bytes()) if result_path.exists() else {'ok': False, 'error': '로그를 확인하세요.'}
    if not success and config['device'].startswith('cuda') and result.get('cudaOutOfMemory'):
        print('실제 모델 실행 중 GPU 메모리가 부족하여 CPU로 다시 측정합니다.', flush=True)
        config.update(device='cpu', dtype='float32')
        save_json(ROOT / 'config/voice_settings.json', config)
        report['selectedProfile'].update(device='cpu', dtype='float32', reason='모델 실행 중 CUDA 메모리 부족으로 CPU로 전환')
        save_json(RUNTIME / 'hardware.json', report)
        success = attempt()
    if not success:
        raise RuntimeError('음성 테스트를 통과하지 못했습니다. runtime/benchmark.json과 setup-benchmark.log를 설치를 맡긴 에이전트에게 보여주세요.')
    result = json.loads(result_path.read_bytes())
    print(f"음성 테스트 완료: 첫 소리 {result['firstChunkMs'] / 1000:.2f}초, "
          f"생성 시간/음성 길이 {result['realTimeFactor']:.2f}배", flush=True)
    if result['realTimeFactor'] >= 1 or result['firstChunkMs'] > 2000:
        print('이 측정에서는 지연이 큽니다. 실제 통화의 문장 사이에도 대기가 생길 수 있습니다.', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inspect', action='store_true', help='사양 확인만 수행; 설치/다운로드 없음')
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--skip-benchmark', action='store_true', help='실제 음성 검증을 생략한 상태로 설치')
    args = parser.parse_args()
    if platform.system() != 'Windows' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('이 설치기는 Windows 11 x64용입니다. Windows ARM 환경은 별도 포팅이 필요합니다.')
    if sys.version_info[:2] != (3, 11) or sys.maxsize <= 2**32:
        raise RuntimeError('64비트 Python 3.11로 실행하세요.')
    RUNTIME.mkdir(exist_ok=True)
    report = inspect_hardware()
    profile = choose_profile(report)
    report['selectedProfile'] = profile
    save_json(RUNTIME / 'hardware.json', report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if args.inspect:
        return
    status = health()
    if status is not None:
        validate_server(status, check_config=False)
        raise RuntimeError('실행 중인 서버가 있습니다. stop-windows.cmd 실행 후 설치를 다시 시작하세요.')
    if report['diskFreeGiB'] < 12:
        raise RuntimeError('설치 공간을 최소 12 GiB 확보하세요. 20 GiB 이상을 권장합니다.')
    if report.get('memoryGiB', 16) < 16:
        print('메모리가 16 GiB 미만입니다. 실행 중 메모리 부족이나 큰 지연이 생길 수 있습니다.', flush=True)
    python, config = prepare_environment(report, profile)
    destination = install_files()
    check_native_host()
    if not args.skip_benchmark:
        benchmark(python, config, report)
    else:
        save_json(RUNTIME / 'benchmark.json', {'ok': False, 'skipped': True})
        print('실제 음성 테스트는 생략됐습니다.', flush=True)
    print(f'\n설치 파일 준비 완료: {destination}\n'
          'Chrome 확장 프로그램 → 개발자 모드 → 압축해제된 확장 프로그램 로드에서 위 폴더를 선택하세요.\n'
          '이미 등록했다면 Dots Voice 카드의 새로고침 버튼을 누르세요.\n'
          'dots 대화 탭에서 Dots Voice 버튼 → 연결 완료 후 통화를 시작하세요.', flush=True)
    if not args.no_open:
        os.startfile(str(destination))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
