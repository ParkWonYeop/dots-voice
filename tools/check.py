"""Run model-free checks from either a checkout or an installation ZIP."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    environment = {**os.environ, 'PYTHONPATH': str(ROOT / 'src'), 'PYTHONUTF8': '1'}
    commands = [
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', '*_test.py'],
        [sys.executable, 'tests/tts_bridge_test.py'],
        [sys.executable, '-m', 'compileall', '-q', 'src', 'tools', 'tests'],
    ]
    if shutil.which('node'):
        commands += [['node', str(path.relative_to(ROOT))] for path in sorted((ROOT / 'tests').glob('*.test.cjs'))]
        commands += [['node', '--check', str(path.relative_to(ROOT))] for path in sorted((ROOT / 'chrome-extension').glob('*.js'))]
    else:
        print('Node.js unavailable: JavaScript checks skipped.', flush=True)
    for command in commands:
        print(' '.join(command), flush=True)
        subprocess.run(command, cwd=ROOT, env=environment, check=True)
    print('All available model-free checks passed. Live Chrome calls require a separate check.', flush=True)


if __name__ == '__main__':
    main()
