"""Native protocol and launcher safety checks; no model or microphone required."""
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import voice_launcher as launcher


class Fragmented(io.BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 2))


class LauncherTests(unittest.TestCase):
    def test_ping_never_starts_model_or_reads_server_token(self):
        with patch.object(launcher, 'ensure_server') as start, patch.object(launcher, 'authenticated_post') as post:
            self.assertEqual(launcher.handle({'type': 'ping'}), {'service': launcher.SERVICE, 'protocol': 1})
            start.assert_not_called()
            post.assert_not_called()

    def test_fragmented_message_and_eof(self):
        data = json.dumps({'type': 'start', 'id': 3}).encode()
        source = Fragmented(struct.pack('=I', len(data)) + data)
        self.assertEqual(launcher.read_message(source), {'type': 'start', 'id': 3})
        self.assertIsNone(launcher.read_message(source))

    def test_oversized_and_truncated_messages(self):
        with self.assertRaises(ValueError):
            launcher.read_message(io.BytesIO(struct.pack('=I', launcher.MAX_MESSAGE + 1)))
        with self.assertRaises(EOFError):
            launcher.read_message(io.BytesIO(struct.pack('=I', 10) + b'{}'))

    def status(self):
        return {'service': launcher.SERVICE, 'rootId': launcher.root_id(),
                'configDigest': launcher.config_digest(), 'speaker': 'designed_soft',
                'mode': 'speaker_reference'}

    def test_repeated_start_reuses_server_without_loading_model(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(launcher, 'RUNTIME', Path(directory)), \
                patch.object(launcher, 'health', return_value=self.status()), \
                patch.object(launcher.subprocess, 'Popen') as spawn:
            for _ in range(2):
                self.assertTrue(launcher.ensure_server()['reused'])
            spawn.assert_not_called()

    def test_foreign_server_and_changed_config_are_not_reused(self):
        for updates in ({'service': 'other'}, {'rootId': 'other'}, {'configDigest': 'old'}):
            with self.subTest(updates=updates), self.assertRaises(RuntimeError):
                launcher.validate_server({**self.status(), **updates})

    def test_bad_native_origin_rejected_before_commands(self):
        with patch.object(launcher, 'handle') as handle:
            with self.assertRaises(ValueError):
                launcher.native_main('chrome-extension://untrusted/')
            handle.assert_not_called()

    def test_failed_server_can_still_be_stopped(self):
        status = {**self.status(), 'error': 'model failure'}
        with self.assertRaises(RuntimeError):
            launcher.validate_server(status)
        launcher.validate_server(status, check_config=False)

    def test_unknown_commands_and_malformed_offers_never_send(self):
        with patch.object(launcher, 'authenticated_post') as send:
            for message in ({'type': 'shell'}, {'type': 'offer', 'offer': {'type': 'answer'}},
                            {'type': 'offer', 'offer': {'type': 'offer', 'sdp': 'bad'}}):
                with self.assertRaises(ValueError):
                    launcher.handle(message)
            send.assert_not_called()

    def test_token_never_returned_in_start_response(self):
        with patch.object(launcher, 'ensure_server', return_value={'reused': True, 'speaker': 'designed_soft'}):
            result = launcher.handle({'type': 'start'})
            self.assertNotIn('token', result)
            self.assertNotIn('url', result)


if __name__ == '__main__':
    unittest.main()
