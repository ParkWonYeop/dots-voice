"""Portable tests for hardware policy, Windows registration, cancellation and PCM."""
import errno
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import hardware_profile as hardware
import setup_windows as setup
import voice_launcher as launcher
from tts_torch_engine import TorchEngine


class HardwareTests(unittest.TestCase):
    def test_no_gpu_low_memory_and_old_driver_stay_on_cpu(self):
        for report in ({}, {'nvidia': [{'vramMiB': 4096}], 'driverCudaVersion': '13.0'},
                       {'nvidia': [{'vramMiB': 8192}], 'driverCudaVersion': '12.7'}):
            with self.subTest(report=report):
                self.assertEqual(hardware.choose_profile(report)['wheel'], 'cpu')

    def test_gpu_selection_is_provisional_until_real_torch_probe(self):
        profile = hardware.choose_profile({'nvidia': [{'vramMiB': 8192}], 'driverCudaVersion': '12.8',
                                           'physicalCores': 12})
        self.assertEqual(profile['wheel'], 'cu128')
        self.assertEqual(profile['device'], 'cpu')
        self.assertEqual(profile['cpuThreads'], 8)

    def test_inventory_failure_keeps_cpu_fallback_and_records_missing_data(self):
        with patch.object(hardware.subprocess, 'run', side_effect=FileNotFoundError), \
                patch.object(hardware.shutil, 'which', return_value=None):
            report = hardware.inspect_hardware()
        self.assertIn('inventoryNote', report)
        self.assertNotIn('memoryGiB', report)
        self.assertEqual(hardware.choose_profile(report)['device'], 'cpu')

    def test_cuda_runtime_failure_falls_back_to_working_cpu(self):
        torch = MagicMock()
        torch.cuda.is_available.return_value = True
        torch.cuda.device_count.return_value = 1
        torch.cuda.get_device_properties.side_effect = RuntimeError('driver failure')
        torch.isfinite.return_value.all.return_value = True
        torch.__version__ = '2.10.0+cu128'
        with patch.dict(sys.modules, {'torch': torch}):
            result = hardware.probe_torch()
        self.assertEqual(result['device'], 'cpu')
        self.assertEqual(result['dtype'], 'float32')


class WindowsIntegrationTests(unittest.TestCase):
    def test_windows_start_uses_venv_python_and_detaches_without_unix_flags(self):
        with tempfile.TemporaryDirectory(prefix='voice path ') as directory:
            root = Path(directory)
            python = root / '.tts-venv/Scripts/python.exe'
            python.parent.mkdir(parents=True); python.touch()
            with patch.object(launcher, 'ROOT', root), patch.object(launcher, 'RUNTIME', root / 'runtime'), \
                    patch.object(launcher, 'WINDOWS', True), patch.object(launcher, 'lock_start'), \
                    patch.object(launcher, 'health', side_effect=[None, {'speaker': 'designed_soft', 'mode': 'speaker_reference'}]), \
                    patch.object(launcher, 'validate_server'), patch.object(launcher.socket, 'socket'), \
                    patch.object(launcher.subprocess, 'Popen') as popen, \
                    patch.object(launcher.subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True), \
                    patch.object(launcher.subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x00000200, create=True):
                self.assertFalse(launcher.ensure_server(timeout=1)['reused'])
            self.assertEqual(popen.call_args.args[0][0], str(python))
            self.assertEqual(popen.call_args.args[0][-1], str(root / 'src/tts_bridge_server.py'))
            self.assertEqual(popen.call_args.kwargs['creationflags'], 0x08000200)
            self.assertNotIn('start_new_session', popen.call_args.kwargs)

    def test_registration_uses_only_current_user_and_supports_unicode_spaces(self):
        registry = MagicMock()
        registry.KEY_SET_VALUE = 2
        registry.KEY_WOW64_32KEY = 512
        registry.KEY_WOW64_64KEY = 256
        with tempfile.TemporaryDirectory(prefix='유니코드 path ') as directory:
            runtime = Path(directory) / 'runtime'
            with patch.dict(sys.modules, {'winreg': registry}), patch.object(setup, 'RUNTIME', runtime):
                destination = setup.install_files()
            self.assertTrue((destination / 'dots-tts.js').exists())
            manifest = json.loads((runtime / (launcher.HOST + '.json')).read_bytes())
            self.assertEqual(manifest['allowed_origins'], [f'chrome-extension://{launcher.extension_id()}/'])
            self.assertEqual(Path(manifest['path']).parent, runtime)
            self.assertIn(b'"%~dp0..\\.tts-venv\\Scripts\\python.exe"', Path(manifest['path']).read_bytes())
            self.assertIn(b'2>>"%~dp0native-host.log"', Path(manifest['path']).read_bytes())
            self.assertIn(b'"%~dp0..\\src\\voice_launcher.py"', Path(manifest['path']).read_bytes())
            self.assertEqual(registry.CreateKeyEx.call_args.args[0], registry.HKEY_CURRENT_USER)
            self.assertEqual([call.args[3] for call in registry.CreateKeyEx.call_args_list], [514, 258])
            self.assertEqual(registry.SetValueEx.call_args.args[-1], str(runtime / (launcher.HOST + '.json')))

    def test_native_probe_accepts_only_complete_valid_binary_response(self):
        reply = json.dumps({'id': 'setup-check', 'ok': True,
                            'result': {'service': launcher.SERVICE, 'protocol': 1}}).encode()
        packet = struct.pack('=I', len(reply)) + reply
        cases = [(0, packet, True), (1, b'', False), (0, b'', False),
                 (0, packet + b'extra log on stdout', False), (0, packet[:-1], False)]
        with tempfile.TemporaryDirectory(prefix='유니코드 path ') as directory:
            runtime = Path(directory)
            setup.save_json(runtime / (launcher.HOST + '.json'),
                            {'path': str(runtime / 'chrome-voice-host.cmd'),
                             'allowed_origins': [f'chrome-extension://{launcher.extension_id()}/']})
            for exit_code, stdout, valid in cases:
                with self.subTest(exit_code=exit_code, stdout=stdout), \
                        patch.object(setup, 'RUNTIME', runtime), patch('builtins.print'), \
                        patch.object(setup.subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True), \
                        patch.object(setup.subprocess, 'run', return_value=SimpleNamespace(
                            returncode=exit_code, stdout=stdout, stderr=b'')) as run:
                    if valid:
                        setup.check_native_host()
                    else:
                        with self.assertRaises(RuntimeError):
                            setup.check_native_host()
                    sent = launcher.read_message(io.BytesIO(run.call_args.kwargs['input']))
                    self.assertEqual(sent['type'], 'ping')
                    report = json.loads((runtime / 'native-host-check.json').read_bytes())
                    self.assertEqual(report['ok'], valid)
                    self.assertFalse(report['chromeVerified'])

    def test_windows_lock_contention_is_retryable(self):
        crt = MagicMock()
        with tempfile.TemporaryFile() as stream, patch.object(launcher, 'WINDOWS', True), \
                patch.dict(sys.modules, {'msvcrt': crt}):
            stream.write(b'\0'); stream.flush()
            launcher.lock_start(stream)
            self.assertEqual(stream.tell(), 0)
            crt.locking.assert_called_once_with(stream.fileno(), crt.LK_NBLCK, 1)
            crt.locking.side_effect = OSError(errno.EACCES, 'locked')
            with self.assertRaises(BlockingIOError):
                launcher.lock_start(stream)

    def test_native_binary_mode_and_korean_message_framing(self):
        command = json.dumps({'id': 10, 'type': 'start'}).encode()
        stdin = SimpleNamespace(buffer=io.BytesIO(struct.pack('=I', len(command)) + command), fileno=lambda: 0)
        stdout = SimpleNamespace(buffer=io.BytesIO(), fileno=lambda: 1)
        crt = MagicMock()
        with patch.object(launcher, 'WINDOWS', True), patch.dict(sys.modules, {'msvcrt': crt}), \
                patch.object(launcher.sys, 'stdin', stdin), patch.object(launcher.sys, 'stdout', stdout), \
                patch.object(launcher.os, 'O_BINARY', 0x8000, create=True), \
                patch.object(launcher, 'handle', return_value={'value': '첫 줄\r\n다음 줄'}):
            launcher.native_main(f'chrome-extension://{launcher.extension_id()}/')
        self.assertEqual(crt.setmode.call_count, 2)
        stdout.buffer.seek(0)
        result = launcher.read_message(stdout.buffer)
        self.assertEqual(result['id'], 10)
        self.assertEqual(result['result']['value'], '첫 줄\r\n다음 줄')
        self.assertIsNone(launcher.read_message(stdout.buffer))


class BenchmarkTests(unittest.TestCase):
    def test_real_cuda_oom_retries_on_cpu_and_updates_saved_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); runtime = root / 'runtime'; runtime.mkdir(); (root / 'config').mkdir()
            config = {'device': 'cuda:0', 'dtype': 'float16'}
            report = {'selectedProfile': dict(config)}
            calls = []
            def run(*args, **kwargs):
                calls.append(args)
                if len(calls) == 1:
                    setup.save_json(runtime / 'benchmark.json', {'ok': False, 'cudaOutOfMemory': True})
                    raise subprocess.CalledProcessError(1, args)
                setup.save_json(runtime / 'benchmark.json', {'ok': True, 'firstChunkMs': 100, 'realTimeFactor': .3})
            with patch.object(setup, 'ROOT', root), patch.object(setup, 'RUNTIME', runtime), \
                    patch.object(setup, 'run', side_effect=run), patch('builtins.print'):
                setup.benchmark('python', config, report)
            self.assertEqual(len(calls), 2)
            self.assertEqual(json.loads((root / 'config/voice_settings.json').read_bytes())['device'], 'cpu')
            self.assertEqual(json.loads((runtime / 'hardware.json').read_bytes())['selectedProfile']['dtype'], 'float32')

    def test_other_failure_is_not_silently_treated_as_gpu_shortage(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(setup, 'RUNTIME', Path(directory)), \
                patch.object(setup, 'run', side_effect=subprocess.CalledProcessError(1, 'python')) as run, \
                patch('builtins.print'):
            with self.assertRaises(RuntimeError):
                setup.benchmark('python', {'device': 'cuda:0'}, {})
            self.assertEqual(run.call_count, 1)


class TorchAudioTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((Path(__file__).resolve().parents[1] / 'config/voice_settings.windows.json').read_bytes())
        self.engine = TorchEngine(self.config)
        self.engine.device = 'cpu'
        self.engine.torch = MagicMock()
        self.engine.prompt = object()
        self.callback = None
        self.hook = MagicMock()
        def register(callback):
            self.callback = callback
            return self.hook
        self.model = MagicMock()
        self.model.model.talker.register_forward_pre_hook.side_effect = register
        self.engine.model = self.model

    def tearDown(self):
        self.engine.shutdown()

    def test_cached_voice_and_full_phrase_pcm_are_finite_and_resampled(self):
        speech = (.2 * np.sin(2 * np.pi * 330 * np.arange(24000) / 24000)).astype(np.float32)
        self.model.generate_voice_clone.return_value = ([speech], 24000)
        audio = []
        result = self.engine.generate('테스트 문장.', audio.append, lambda: False)
        self.assertEqual(sum(map(len, audio)), 48000)
        self.assertTrue(np.isfinite(np.concatenate(audio)).all())
        self.assertEqual(result['synthesisMode'], 'phrase')
        self.assertEqual(result['generatedSeconds'], 1)
        self.assertIs(self.model.generate_voice_clone.call_args.kwargs['voice_clone_prompt'], self.engine.prompt)
        self.assertNotIn('stream', self.model.generate_voice_clone.call_args.kwargs)
        self.hook.remove.assert_called_once()

    def test_interrupt_aborts_at_next_forward_without_leaking_hook_or_audio(self):
        cancelled = [False]
        def generate(**kwargs):
            self.callback(None, ())
            cancelled[0] = True
            self.callback(None, ())
            raise AssertionError('Cancellation should have interrupted generation')
        self.model.generate_voice_clone.side_effect = generate
        audio = []
        self.assertIsNone(self.engine.generate('중단될 문장.', audio.append, lambda: cancelled[0]))
        self.assertEqual(audio, [])
        self.hook.remove.assert_called_once()

    def test_hook_removed_even_when_model_fails(self):
        self.model.generate_voice_clone.side_effect = RuntimeError('model error')
        with self.assertRaises(RuntimeError):
            self.engine.generate('오류.', lambda pcm: None, lambda: False)
        self.hook.remove.assert_called_once()


if __name__ == '__main__':
    unittest.main()
