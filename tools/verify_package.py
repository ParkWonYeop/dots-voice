"""Verify ZIP contents and exercise the packaged native host without a model."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile


def verify(path):
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or archive.testzip() is not None:
            raise ValueError('Duplicate or corrupt ZIP member')
        roots = {PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1 or roots.pop() != path.stem:
            raise ValueError('Unexpected package root')
        prefix = path.stem + '/'
        for entry in entries:
            parts = PurePosixPath(entry.filename).parts
            if entry.filename.startswith('/') or '..' in parts or '\\' in entry.filename:
                raise ValueError('Unsafe archive path')
            if any(part in {'.git', '.env', '.tts-venv', 'runtime', 'models', 'artifacts', '__pycache__'} for part in parts):
                raise ValueError('Runtime or private files must not be packaged')
            if not stat.S_ISREG(entry.external_attr >> 16):
                raise ValueError('Package must contain only regular files')
            if entry.filename.endswith('.command') and not (entry.external_attr >> 16) & stat.S_IXUSR:
                raise ValueError('macOS launcher lost its executable permission')
        sums = archive.read(prefix + 'SHA256SUMS.txt').decode().splitlines()
        expected = {line.split('  ', 1)[1]: line.split('  ', 1)[0] for line in sums}
        actual = {name[len(prefix):] for name in names} - {'SHA256SUMS.txt'}
        if set(expected) != actual:
            raise ValueError('Checksum manifest does not cover the entire package')
        for name, digest in expected.items():
            if hashlib.sha256(archive.read(prefix + name)).hexdigest() != digest:
                raise ValueError(f'Checksum mismatch: {name}')
        for name in ('README.md', 'SETUP.md', 'AGENTS.md', 'CLAUDE.md', 'AGENT_PROMPT.txt',
                     'src/voice_launcher.py', 'chrome-extension/dots-tts.js',
                     'chrome-extension/transcript_buffer.js', 'tools/check.py'):
            if name not in actual:
                raise ValueError(f'Missing installation file: {name}')
        info = json.loads(archive.read(prefix + 'PACKAGE_INFO.json'))
        if not re.fullmatch(r'[0-9a-f]{40}', info['sourceCommit']):
            raise ValueError('Invalid source commit')
        config = json.loads(archive.read(prefix + 'config/voice_settings.json'))
        if hashlib.sha256(archive.read(prefix + config['referenceAudio'])).hexdigest() != config['referenceSha256']:
            raise ValueError('Voice reference mismatch')
        windows = path.stem.endswith('Windows11')
        if (config.get('backend') == 'torch') != windows:
            raise ValueError('Wrong platform configuration')
        if windows:
            for name in ('install-windows.cmd', 'stop-windows.cmd'):
                data = archive.read(prefix + name)
                if b'\n' in data.replace(b'\r\n', b''):
                    raise ValueError('Windows launcher must use CRLF')
        with tempfile.TemporaryDirectory(prefix='dots package ') as directory:
            archive.extractall(directory)
            root = Path(directory) / path.stem
            manifest = json.loads((root / 'chrome-extension/manifest.json').read_bytes())
            import base64
            digest = hashlib.sha256(base64.b64decode(manifest['key'])).hexdigest()[:32]
            extension = ''.join(chr(ord('a') + int(char, 16)) for char in digest)
            message = json.dumps({'id': 'package-check', 'type': 'ping'}).encode()
            for launcher in ('src/voice_launcher.py', 'voice_launcher.py'):
                result = subprocess.run([sys.executable, str(root / launcher), f'chrome-extension://{extension}/'],
                                        cwd=directory, input=struct.pack('=I', len(message)) + message,
                                        capture_output=True, timeout=15, check=True)
                if len(result.stdout) < 4 or struct.unpack('=I', result.stdout[:4])[0] != len(result.stdout) - 4:
                    raise ValueError('Packaged native host returned an invalid message')
                if json.loads(result.stdout[4:]) != {
                    'id': 'package-check', 'ok': True, 'result': {'service': 'dots-local-tts-v1', 'protocol': 1}
                }:
                    raise ValueError('Packaged native host ping failed')
            subprocess.run([sys.executable, '-m', 'compileall', '-q', str(root / 'src')], check=True)
    print(f'{path.name}: {len(names)} files, hashes, platform settings and native host ping passed; '
          f'dirty={info["sourceWorkingTreeDirty"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archives', nargs='+', type=Path)
    for path in parser.parse_args().archives:
        verify(path)


if __name__ == '__main__':
    main()
