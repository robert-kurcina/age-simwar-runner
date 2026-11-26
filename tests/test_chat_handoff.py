"""Public synthetic campaign handoff regression tests."""
import tempfile
import unittest
from pathlib import Path

import age_runtime.core.chat_handoff as chat_handoff
from age_runtime.core.play import start, update

REV = '51b44e167905a0d0ec8b556c2791edd49c57b85a'
MANIFEST = Path(__file__).resolve().parents[1] / 'campaigns/civic-recovery/campaign.json'


class HandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.session = update(start(MANIFEST, 'service-restoration'), actor='coordinator', turns=1)

    def test_roundtrip_replay(self):
        envelope = chat_handoff.package(self.session, REV)
        self.assertEqual(chat_handoff.unpack(envelope, REV), self.session)

    def test_revision_mismatch(self):
        with self.assertRaisesRegex(ValueError, 'engine revision mismatch'):
            chat_handoff.unpack(chat_handoff.package(self.session, REV), '0' * 40)

    def test_payload_tampering(self):
        envelope = chat_handoff.package(self.session, REV)
        envelope['payload']['session']['state']['turn'] = 999
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            chat_handoff.unpack(envelope, REV)

    def test_rehashed_invalid_checkpoint(self):
        envelope = chat_handoff.package(self.session, REV)
        envelope['payload']['session']['state']['turn'] = 999
        envelope['payload']['session_digest'] = chat_handoff.digest(envelope['payload']['session'])
        envelope['payload_digest'] = chat_handoff.digest(envelope['payload'])
        with self.assertRaises(ValueError):
            chat_handoff.unpack(envelope, REV)

    def test_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'handoff.json'
            envelope = chat_handoff.package(self.session, REV)
            chat_handoff.write_new(out, envelope)
            with self.assertRaises(FileExistsError):
                chat_handoff.write_new(out, envelope)
            self.assertEqual(chat_handoff.unpack(chat_handoff.read(out), REV), self.session)

    def test_bad_revision(self):
        with self.assertRaisesRegex(ValueError, '40-character'):
            chat_handoff.package(self.session, 'main')


if __name__ == '__main__':
    unittest.main()
