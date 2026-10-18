import json
import tempfile
import unittest
from pathlib import Path
from core import ControlError
from lsc_identity import import_identity


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = self.root / "module.json"
        self.identity = {"defaults":{"clientId":"synthetic-client","lang":"fr"},
                         "portable_signing_key":"synthetic-signing-key-for-tests"}

    def write(self, data):
        self.source.write_text(json.dumps(data),encoding="utf-8")

    def test_import_stays_in_local_profile(self):
        self.write(self.identity)
        target=import_identity(self.source,self.root/"profile")
        self.assertEqual(json.loads(target.read_text()),self.identity)
        self.assertFalse(target.with_suffix(".tmp").exists())

    def test_session_and_device_credentials_are_rejected(self):
        for key in ("sid","ecode","localKey","password","token"):
            with self.subTest(key=key):
                self.write(dict(self.identity,**{key:"DO-NOT-IMPORT"}))
                with self.assertRaises(ControlError): import_identity(self.source,self.root/"profile")
                self.write(dict(self.identity,defaults={key:"DO-NOT-IMPORT"}))
                with self.assertRaises(ControlError): import_identity(self.source,self.root/"profile")
        self.assertFalse((self.root/"profile").exists())

    def test_invalid_module_does_not_replace_existing_module_or_repeat_secret(self):
        self.write(self.identity)
        target=import_identity(self.source,self.root/"profile")
        before=target.read_bytes()
        self.write({"defaults":{},"portable_signing_key":"SECRET"})
        with self.assertRaises(ControlError) as error: import_identity(self.source,self.root/"profile")
        self.assertNotIn("SECRET",str(error.exception))
        self.assertEqual(target.read_bytes(),before)
