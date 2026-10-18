"""Publication checks distinguish actual credential material from parser constants."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from check_publication import TOKEN, identity_secrets


class PublicationTests(unittest.TestCase):
    def test_github_token_is_detected(self):
        self.assertIsNotNone(TOKEN.search(b"ghp_"+b"A"*36))

    def test_full_private_key_is_detected(self):
        data=b"-----BEGIN "+b"PRIVATE KEY-----\n"+(b"A"*64+b"\n")*3+b"-----END PRIVATE KEY-----"
        self.assertIsNotNone(TOKEN.search(data))

    def test_tls_parser_header_literal_is_not_a_private_key(self):
        self.assertIsNone(TOKEN.search(b"-----BEGIN "+b"PRIVATE KEY-----\0supported TLS format"))

    def test_timezone_is_public_but_signing_material_is_private(self):
        result=identity_secrets({"defaults":{"timeZoneId":"Asia/Shanghai","clientId":"synthetic-client-id"},
                                 "portable_signing_key":"synthetic-signing-material"})
        self.assertCountEqual(result,["synthetic-client-id","synthetic-signing-material"])
