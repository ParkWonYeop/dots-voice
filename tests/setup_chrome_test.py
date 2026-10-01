"""Exercise the installed macOS host with real framed messages and quoted paths."""
import io
import json
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import setup_chrome as setup
import voice_launcher as launcher


@unittest.skipIf(sys.platform == 'win32', 'macOS/POSIX shell bootstrap')
class MacHostTests(unittest.TestCase):
    def test_application_data_bootstrap_protocol_and_error_log(self):
        with tempfile.TemporaryDirectory(prefix='dots host ') as directory:
            home = Path(directory) / "사용자 O'Brien"
            root = home / 'Documents/voice project'
            root.mkdir(parents=True)
            (root / 'src').mkdir()
            shutil.copy2(setup.ROOT / 'src/voice_launcher.py', root / 'src/voice_launcher.py')
            shutil.copytree(setup.ROOT / 'chrome-extension', root / 'chrome-extension')
            python = root / '.tts-venv/bin/python'
            python.parent.mkdir(parents=True)
            python.symlink_to(Path(sys.executable).resolve())
            with patch.object(setup, 'ROOT', root), patch.object(setup, 'RUNTIME', root / 'runtime'), \
                    patch.object(setup.Path, 'home', return_value=home):
                setup.install_files()
            manifest = json.loads((home / 'Library/Application Support/Google/Chrome/NativeMessagingHosts' /
                                   (launcher.HOST + '.json')).read_bytes())
            wrapper = Path(manifest['path'])
            self.assertEqual(wrapper.parent, home / 'Library/Application Support/Dots Voice')
            self.assertEqual(stat.S_IMODE(wrapper.stat().st_mode), 0o700)
            data = json.dumps({'id': 11, 'type': 'unknown-diagnostic-command'}).encode()
            result = subprocess.run([str(wrapper), manifest['allowed_origins'][0]], cwd=wrapper.parent,
                                    input=struct.pack('=I', len(data)) + data, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stderr, b'')
            reply = launcher.read_message(io.BytesIO(result.stdout))
            self.assertEqual(reply, {'id': 11, 'ok': False, 'error': 'Unknown command'})
            # An early Python failure must remain diagnosable instead of only
            # Chrome's generic "Native host has exited" message.
            (root / 'src/voice_launcher.py').rename(root / 'src/voice_launcher.moved.py')
            failed = subprocess.run([str(wrapper), manifest['allowed_origins'][0]],
                                    input=b'', capture_output=True, timeout=10)
            self.assertNotEqual(failed.returncode, 0)
            self.assertEqual(failed.stdout, b'')
            self.assertIn("can't open file", (wrapper.parent / 'native-host.log').read_text(encoding='utf-8'))
            self.assertEqual(stat.S_IMODE((wrapper.parent / 'native-host.log').stat().st_mode), 0o600)


if __name__ == '__main__':
    unittest.main()
