"""Synthetic signing resources; no vendor or account identities in fixtures."""
import struct
import unittest

from connection_crypto import ResourceError, _interpolate_zero, recover_picture_secrets


def picture_fixture(key="synthetic_application", secrets=(b"synthetic-resource-material-12345",)):
    pixels = bytearray(65536)
    hashed = 0
    for byte in key.encode("ascii"):
        hashed = (31 * hashed + byte) & 0xffffffff
    signed = hashed if hashed < 0x80000000 else hashed - 0x100000000
    start = (abs(signed) % len(pixels)) >> 1
    count = 4 * len(secrets)
    pixels[start + 1:start + 3] = bytes((len(secrets), count))
    pixels[start + 3:start + 7] = (40000 ^ start).to_bytes(4, "big")
    for index in range(count):
        position = previous = 40000 + 1000 * index
        x = index % 4 + 1
        secret = int.from_bytes(secrets[index // 4], "big")
        y = secret + 7*x + 11*x*x + 13*x*x*x
        for value in (x, y):
            encoded = value.to_bytes((value.bit_length() + 7) // 8, "big")
            pixels[position] = len(encoded)
            position += 1
            pixels[position:position + len(encoded)] = encoded
            position += len(encoded)
        following = 40000 + 1000 * ((index + 1) % count)
        pixels[position:position + 4] = (following ^ previous).to_bytes(4, "big")
    header = bytearray(54)
    header[:2] = b"BM"
    struct.pack_into("<I", header, 2, len(header) + len(pixels))
    struct.pack_into("<I", header, 10, 54)
    struct.pack_into("<H", header, 28, 24)
    return bytes(header + pixels)


class ResourceTests(unittest.TestCase):
    def test_recover_independent_polynomial_groups(self):
        secrets = (b"first synthetic secret", b"second synthetic secret")
        self.assertEqual(recover_picture_secrets("synthetic_application",
                         picture_fixture(secrets=secrets)), list(secrets))

    def test_wrong_application_key_is_rejected(self):
        with self.assertRaises(ResourceError):
            recover_picture_secrets("different_key", picture_fixture())

    def test_duplicate_points_are_rejected(self):
        with self.assertRaises(ResourceError):
            _interpolate_zero([(1, 4), (1, 9)])

    def test_nonintegral_result_is_rejected(self):
        with self.assertRaises(ResourceError):
            _interpolate_zero([(1, 1), (3, 2)])

    def test_bad_bitmap_headers_are_rejected(self):
        original = picture_fixture()
        for offset, value in ((0, 0), (10, 55), (28, 16), (30, 1)):
            with self.subTest(offset=offset):
                picture = bytearray(original)
                picture[offset] = value
                with self.assertRaises(ResourceError):
                    recover_picture_secrets("synthetic_application", bytes(picture))
        with self.assertRaises(ResourceError):
            recover_picture_secrets("synthetic_application", original[:-1])

    def test_empty_and_oversized_inputs_are_rejected(self):
        for picture in (b"", bytes(2 * 1024 * 1024 + 1)):
            with self.assertRaises(ResourceError):
                recover_picture_secrets("synthetic_application", picture)


if __name__ == "__main__":
    unittest.main()
