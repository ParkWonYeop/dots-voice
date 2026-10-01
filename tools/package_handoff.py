"""Build reproducible, allowlisted Mac and Windows installation ZIPs."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMMON = [
    '.gitignore', 'voice_launcher.py',
    'src/audio_stream.py', 'src/voice_launcher.py',
    'src/tts_bridge_server.py', 'src/tts_worker.py',
    'config/voice_candidates.json', 'voices/designed-soft.json', 'voices/designed-soft.wav',
    'tests/voice_launcher_test.py', 'tests/tts_bridge_test.py',
    'tests/transcript_buffer.test.cjs', 'tests/chrome_extension.test.cjs',
    'tools/check.py', 'tools/verify_package.py',
    'chrome-extension/manifest.json', 'chrome-extension/background.js',
    'chrome-extension/page-api.js', 'chrome-extension/popup.html',
    'chrome-extension/popup.css', 'chrome-extension/popup.js',
    'chrome-extension/dots-tts.js', 'chrome-extension/transcript_buffer.js',
    'chrome-extension/icon-16.png', 'chrome-extension/icon-32.png',
    'chrome-extension/icon-48.png', 'chrome-extension/icon-128.png',
]
PLATFORM = {
    'mac': ['Dots Voice 설치.command', 'Dots Voice 종료.command', 'src/setup_chrome.py',
            'requirements/requirements.tts.lock.txt', 'tests/setup_chrome_test.py'],
    'windows': ['install-windows.cmd', 'stop-windows.cmd', 'src/setup_windows.py',
                'src/hardware_profile.py', 'src/tts_torch_engine.py', 'src/tts_diagnose.py',
                'requirements/requirements.windows.txt', 'requirements/requirements.windows.lock.txt',
                'config/voice_settings.windows.json', 'tests/windows_setup_test.py'],
}
DOCS = ('README.md', 'AGENTS.md', 'CLAUDE.md', 'SETUP.md', 'AGENT_PROMPT.txt')


def build(platform, destination, allow_dirty=False):
    windows = platform == 'windows'
    package = 'Dots-Voice-Windows11' if windows else 'Dots-Voice-Mac'
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip())
    if dirty and not allow_dirty:
        raise ValueError('Commit all changes before building a release (or use --allow-dirty for a local check).')
    sources = {name: name for name in COMMON + PLATFORM[platform]}
    sources.update({name: f'packaging/{"windows" if windows else "macos"}/{name}' for name in DOCS})
    sources['config/voice_settings.json'] = 'config/voice_settings.windows.json' if windows else 'config/voice_settings.json'
    payload = {}
    for name, source in sources.items():
        path = ROOT / source
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Missing or non-regular package source: {source}')
        data = path.read_bytes()
        if path.suffix not in ('.wav', '.png') and b'/Users/' in data:
            raise ValueError(f'Personal absolute path in package source: {source}')
        payload[name] = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n') if name.endswith('.cmd') else data
    config = json.loads(payload['config/voice_settings.json'])
    reference_hash = hashlib.sha256(payload[config['referenceAudio']]).hexdigest()
    if reference_hash != config['referenceSha256']:
        raise ValueError('Selected voice reference has changed')
    manifest = json.loads(payload['chrome-extension/manifest.json'])
    info = {
        'package': package, 'version': manifest['version'], 'extensionVersion': manifest['version'],
        'sourceCommit': commit, 'sourceWorkingTreeDirty': dirty,
        'platform': 'Windows 11 x64' if windows else 'macOS Apple Silicon (arm64)', 'python': '3.11',
        'synthesisMode': 'phrase' if windows else 'streaming',
        'model': config['model'], 'modelRevision': config['revision'],
        'referenceSha256': reference_hash, 'modelWeightsIncluded': False,
    }
    payload['PACKAGE_INFO.json'] = (json.dumps(info, ensure_ascii=False, indent=2) + '\n').encode()
    payload['SHA256SUMS.txt'] = ''.join(
        f'{hashlib.sha256(data).hexdigest()}  {name}\n' for name, data in sorted(payload.items())
    ).encode()
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / (package + '.zip')
    temporary = archive_path.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(payload.items()):
            member = zipfile.ZipInfo(f'{package}/{name}', date_time=(2026, 10, 1, 0, 0, 0))
            member.create_system = 3
            member.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if name.endswith('.command') else 0o644
            member.external_attr = (stat.S_IFREG | mode) << 16
            archive.writestr(member, data)
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP integrity check failed')
    temporary.replace(archive_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    print(json.dumps({'path': str(archive_path), 'files': len(payload), 'dirty': dirty,
                      'bytes': archive_path.stat().st_size, 'sha256': digest}, ensure_ascii=False))
    return archive_path, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=('all', 'mac', 'windows'), default='all')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'artifacts')
    parser.add_argument('--allow-dirty', action='store_true', help='For local verification only; never publish these ZIPs')
    args = parser.parse_args()
    platforms = ('mac', 'windows') if args.platform == 'all' else (args.platform,)
    archives = [build(platform, args.output_dir, args.allow_dirty) for platform in platforms]
    (args.output_dir / 'SHA256SUMS.txt').write_text(''.join(f'{digest}  {path.name}\n' for path, digest in archives))


if __name__ == '__main__':
    main()
