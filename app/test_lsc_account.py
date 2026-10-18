import json
import unittest
from unittest.mock import patch, MagicMock
from core import ControlError
from lsc_account import LSCAccount


class Store:
    def __init__(self):
        self.secrets = {}
        self.config = {}
    def secret(self, key): return self.secrets.get(key, "")
    def set_secret(self, key, value): self.secrets[key] = value
    def load(self): return dict(self.config)
    def save(self, value): self.config = value


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.account = LSCAccount(self.store, restore=False,use_portable=False)

    def test_waiting_qr_does_not_save_session(self):
        with patch.object(self.account, "request", return_value=None):
            self.assertFalse(self.account.poll_qr("example-token"))
        self.assertEqual(self.store.secrets, {})

    def test_qr_consent_saves_only_session_credentials(self):
        user = {"sid":"session", "ecode":"encryption", "email":"private@example.com"}
        with patch.object(self.account, "request", return_value=user):
            self.assertTrue(self.account.poll_qr("example-token"))
        self.assertEqual(json.loads(self.store.secrets["lsc_session:eu"]),
                         {"sid":"session", "ecode":"encryption"})
        self.assertTrue(self.account.connected)

    def test_device_list_requires_phone_consent(self):
        with patch.object(self.account, "request") as request:
            with self.assertRaises(ControlError): self.account.devices()
        request.assert_not_called()

    def test_metadata_never_contains_cloud_or_local_credentials(self):
        device = {"devId":"bulb", "name":"Lampe RGB", "dps":{"20":True},
                  "localKey":"a-local-key", "sid":"never-persist", "privateKey":"private"}
        self.account.remember_devices([device])
        public = json.dumps(self.store.config)
        for value in ("a-local-key", "never-persist", "private"):
            self.assertNotIn(value, public)
        self.assertEqual(self.store.secrets["lsc_local:bulb"], "a-local-key")

    def test_device_lists_keep_the_home_association(self):
        self.account.session = {"sid":"s", "ecode":"e"}
        with patch.object(self.account, "request", side_effect=[
            [{"groupId":42,"name":"Maison"}], [{"devId":"bulb","name":"Lampe RGB"}]]) as request:
            devices = self.account.devices()
        self.assertEqual(devices[0]["_home_id"], 42)
        self.assertEqual(request.call_args.kwargs["gid"], 42)

    def test_native_output_leak_is_rejected_without_repeating_it(self):
        process = MagicMock()
        process.returncode = 0
        process.communicate.return_value = ('secret: DO-NOT-REPEAT\n{}\n', None)
        self.account.process = process
        with patch.object(self.account, "_start"):
            with self.assertRaises(ControlError) as failure:
                self.account.create_qr()
        self.assertNotIn("DO-NOT-REPEAT", str(failure.exception))

    def test_response_signature_error_never_displays_payload(self):
        process = MagicMock()
        process.returncode = 0
        process.communicate.return_value = (json.dumps(
            {"id":1,"ok":False,"error":"RESPONSE_SIGNATURE"}) + '\n', None)
        self.account.process = process
        with patch.object(self.account, "_start"):
            with self.assertRaisesRegex(ControlError, "RESPONSE_SIGNATURE"):
                self.account.create_qr()

    def test_new_helper_is_started_for_every_request(self):
        process = MagicMock()
        process.returncode = 0
        process.communicate.side_effect = [
            (json.dumps({"id":1,"ok":True,"result":"x"*32})+'\n',None),
            (json.dumps({"id":2,"ok":True,"result":None})+'\n',None)]
        def start(): self.account.process = process
        with patch.object(self.account, "_start", side_effect=start) as launch:
            token = self.account.create_qr()
            self.assertFalse(self.account.poll_qr(token))
        self.assertEqual(launch.call_count, 2)


if __name__ == "__main__":
    unittest.main()
