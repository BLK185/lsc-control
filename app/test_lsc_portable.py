import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lsc_portable import (
    LSCPortableTransport, PortableError, decode_response, derive_key,
    encrypt_data, sign_form,
)


class PortableTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.identity_path = Path(self.directory.name) / "identity.json"
        self.signing_key = "synthetic-private-signing-material"
        self.identity_path.write_text(json.dumps({
            "portable_signing_key": self.signing_key,
            "defaults": {"clientId": "test-client", "lang": "fr", "et": "1"},
        }), encoding="utf-8")

    def reply(self, result, key, success=True):
        result = encrypt_data({"success": success, "result": result}, key)
        timestamp = 123456
        signature = hashlib.md5(
            f"result={result}||t={timestamp}||{key.decode('ascii')}".encode()
        ).hexdigest()
        return {"result": result, "t": timestamp, "sign": signature}

    def test_timer_timezone_overrides_the_gaming_client_default(self):
        forms=[]
        def transport(host,form):
            forms.append(form)
            key=derive_key(form['requestId'],self.signing_key)
            return self.reply(True,key)
        client=LSCPortableTransport(self.identity_path,transport=transport)
        try:
            self.assertTrue(client.request('thing.m.clock.dps.add',{},timezone_id='Europe/Paris'))
            self.assertEqual(forms[0]['timeZoneId'],'Europe/Paris')
            with self.assertRaises(PortableError):client.request('thing.m.clock.dps.add',{},timezone_id='bad timezone')
            self.assertEqual(len(forms),1)
        finally:client.close()

    def test_key_uses_request_id_as_hmac_key_and_session_ecode_as_suffix(self):
        expected = hmac.new(b"request-id", b"synthetic-private-signing-material_session-ecode",
                            hashlib.sha256).hexdigest()[:16].encode()
        self.assertEqual(derive_key("request-id", self.signing_key, "session-ecode"), expected)
        self.assertNotEqual(derive_key("request-id", self.signing_key), expected)

    def test_form_signature_sorts_filters_and_reorders_postdata_digest(self):
        digest = hashlib.md5(b"payload").hexdigest()
        rearranged = digest[8:16] + digest[:8] + digest[24:32] + digest[16:24]
        expected = hmac.new(self.signing_key.encode(),
                            f"a=example||postData={rearranged}||v=1.0".encode(),
                            hashlib.sha256).hexdigest()
        self.assertEqual(sign_form({"v": "1.0", "ignored": "anything", "a": "example",
                                    "postData": "payload"}, self.signing_key), expected)

    def test_unicode_encrypted_response_roundtrip(self):
        key = b"0123456789abcdef"
        result = {"name": "Éclairage 🟣", "dps": {"20": True}}
        self.assertEqual(decode_response(self.reply(result, key), key), result)

    def test_tampered_signature_rejected_before_decryption(self):
        with self.assertRaisesRegex(PortableError, "RESPONSE_SIGNATURE"):
            decode_response({"result": "not base64", "t": 1, "sign": "0" * 32},
                            b"0123456789abcdef")

    def test_signed_but_malformed_ciphertext_rejected(self):
        key = b"0123456789abcdef"
        result = "malformed"
        signature = hashlib.md5(f"result={result}||t=1||{key.decode()}".encode()).hexdigest()
        with self.assertRaisesRegex(PortableError, "RESPONSE_DECRYPT"):
            decode_response({"result": result, "t": 1, "sign": signature}, key)

    def test_request_signs_fresh_session_and_decrypts_result(self):
        captured = []
        def wire(host, form):
            captured.append((host, dict(form)))
            key = derive_key(form["requestId"], self.signing_key, "ecode")
            self.assertEqual(form["sign"], sign_form(form, self.signing_key))
            return self.reply([{"name": "Salon"}], key)
        transport = LSCPortableTransport(self.identity_path, transport=wire)
        self.addCleanup(transport.close)
        result = transport.request("tuya.m.location.list", {"test": "é"}, version="4.0",
                                   region="eu", session={"sid": "user-session", "ecode": "ecode"})
        self.assertEqual(result, [{"name": "Salon"}])
        self.assertEqual(captured[0][0], "a1.tuyaeu.com")
        self.assertEqual(captured[0][1]["sid"], "user-session")
        self.assertNotIn("é", captured[0][1]["postData"])

    def test_invalid_api_and_region_never_reach_transport(self):
        wire = MagicMock()
        transport = LSCPortableTransport(self.identity_path, transport=wire)
        self.addCleanup(transport.close)
        for api, region in [("arbitrary.admin", "eu"), ("tuya.m.location.list", "arbitrary.host")]:
            with self.assertRaisesRegex(PortableError, "REQUEST_NOT_ALLOWED"):
                transport.request(api, region=region)
        wire.assert_not_called()

    def test_no_previous_sid_survives_anonymous_request(self):
        captured = []
        def wire(host, form):
            captured.append(form)
            key = derive_key(form["requestId"], self.signing_key)
            return self.reply("synthetic-qr-token", key)
        identity = json.loads(self.identity_path.read_text())
        identity["defaults"]["sid"] = "stale-session"
        self.identity_path.write_text(json.dumps(identity))
        transport = LSCPortableTransport(self.identity_path, transport=wire)
        self.addCleanup(transport.close)
        transport.request("tuya.m.user.qr.token.create")
        self.assertNotIn("sid", captured[0])

    def test_https_is_verified_redirects_disabled_and_body_bounded(self):
        transport = LSCPortableTransport(self.identity_path)
        self.addCleanup(transport.close)
        response = MagicMock()
        response.__enter__.return_value = response
        response.status_code = 200
        response.iter_content.return_value = [b"{}"]
        with patch.object(transport._http, "post", return_value=response) as post:
            self.assertEqual(transport._https("a1.tuyaeu.com", {}), {})
            self.assertTrue(post.call_args.kwargs["verify"])
            self.assertFalse(post.call_args.kwargs["allow_redirects"])
            self.assertEqual(post.call_args.kwargs["timeout"], 20)
        response.iter_content.return_value = [b"a" * 10]
        with patch.object(transport._http, "post", return_value=response), \
                patch("lsc_portable.MAX_RESPONSE_BYTES", 9):
            with self.assertRaisesRegex(PortableError, "RESPONSE_SIZE"):
                transport._https("a1.tuyaeu.com", {})

    def test_identity_failure_does_not_include_secret_values(self):
        self.identity_path.write_text("not-json-private-material")
        with self.assertRaises(PortableError) as caught:
            LSCPortableTransport(self.identity_path)
        self.assertEqual(str(caught.exception), "PORTABLE_IDENTITY")


if __name__ == "__main__":
    unittest.main()
