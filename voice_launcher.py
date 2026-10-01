"""Compatibility entry point for Chrome hosts registered before the source move."""
from pathlib import Path
import runpy
import sys

source = Path(__file__).resolve().parent / 'src'
sys.path.insert(0, str(source))
if __name__ == '__main__':
    runpy.run_path(str(source / 'voice_launcher.py'), run_name='__main__')
else:
    from src import voice_launcher as implementation
    sys.modules[__name__] = implementation
