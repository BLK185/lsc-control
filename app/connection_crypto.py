"""Read the pinned client's signing resource without executing native code.

No application identity is included here. Inputs must come from the verified
official download. The resource stores polynomial shares, indexed by the
application key; interpolation at zero recovers the resource's byte string.
"""
import hashlib
import re
import struct
from fractions import Fraction
from pathlib import Path


NATIVE_SHA256 = "6bc3d29647bebf61fff77713a5dd1b6880c4776ff941eb1f1d37c5bcf4ed1f66"
MAX_PICTURE = 2 * 1024 * 1024


class ResourceError(ValueError):
    """An opaque error, safe to display without resource contents."""


def _interpolate_zero(rows):
    if not rows or len(rows) > 32 or len({x for x, _ in rows}) != len(rows):
        raise ResourceError("SIGNING_SHARES")
    result = Fraction(0)
    for x, y in rows:
        term = Fraction(y)
        for other, _ in rows:
            if other != x:
                term *= Fraction(-other, x - other)
        result += term
    if result.denominator != 1 or result <= 0:
        raise ResourceError("SIGNING_POLYNOMIAL")
    value = int(result)
    # The native reader emits base-16 text, then decodes pairs of hex digits.
    text = format(value, "x")
    if len(text) % 2 or len(text) > 512:
        raise ResourceError("SIGNING_LENGTH")
    return bytes.fromhex(text)


def recover_picture_secrets(application_key, picture):
    """Decode a bounded BMP signing resource; return its recovered byte strings."""
    if (not isinstance(application_key, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", application_key)
            or not isinstance(picture, bytes) or not 0x2800 <= len(picture) <= MAX_PICTURE):
        raise ResourceError("SIGNING_RESOURCE")
    try:
        size, offset = struct.unpack_from("<I4xI", picture, 2)
        depth = struct.unpack_from("<H", picture, 28)[0]
        compression = struct.unpack_from("<I", picture, 30)[0]
    except struct.error:
        raise ResourceError("SIGNING_BITMAP") from None
    if (picture[:2] != b"BM" or size != len(picture) or offset != 54
            or depth not in (24, 32) or compression != 0):
        raise ResourceError("SIGNING_BITMAP")
    pixels = picture[54:]
    length = len(pixels)

    def read(position, count):
        return bytes(pixels[(position + i) % length] for i in range(count))

    def word(position):
        return int.from_bytes(read(position, 4), "big")

    hashed = 0
    for byte in application_key.encode("ascii"):
        hashed = (31 * hashed + byte) & 0xffffffff
    signed = hashed if hashed < 0x80000000 else hashed - 0x100000000
    start = (abs(signed) % length) >> 1
    groups, count = read(start + 1, 2)
    if not 1 <= groups <= 5 or not groups <= count <= 32 or count % groups:
        raise ResourceError("SIGNING_SHARE_COUNT")
    position = (word(start + 3) ^ start) % length
    rows = []
    for _ in range(count):
        previous = position
        pair = []
        for part in range(2):
            width = pixels[position]
            position = (position + 1) % length
            # Native Y lengths are signed bytes. Restrict both fields before
            # allocating/interpolating, rather than reproducing unsafe reads.
            if not 1 <= width <= (127 if part else 255):
                raise ResourceError("SIGNING_SHARE_LENGTH")
            pair.append(int.from_bytes(read(position, width), "big"))
            position = (position + width) % length
        rows.append(tuple(pair))
        position = (word(position) ^ previous) % length
    per_group = count // groups
    return [_interpolate_zero(rows[i * per_group:(i + 1) * per_group])
            for i in range(groups)]


def _profile_prefix(library):
    # This offset belongs only to the exact, verified version of the native
    # library. A changed vendor build must be investigated before accepting it.
    if (not isinstance(library, bytes)
            or hashlib.sha256(library).hexdigest() != NATIVE_SHA256):
        raise ResourceError("SIGNING_LIBRARY_VERSION")
    try:
        pe = struct.unpack_from("<I", library, 60)[0]
        count, optional_size = struct.unpack_from("<H12xH", library, pe + 6)
        sections = pe + 24 + optional_size
        for index in range(count):
            location = sections + 40 * index
            virtual_size, rva, size, raw = struct.unpack_from("<IIII", library, location + 8)
            if rva <= 0x9334 < rva + min(virtual_size, size):
                prefix = library[raw + 0x9334 - rva:raw + 0x9334 - rva + 1]
                if len(prefix) == 1 and prefix.isalpha():
                    return prefix.decode("ascii")
    except (struct.error, UnicodeError):
        pass
    raise ResourceError("SIGNING_LIBRARY_FORMAT")


def signing_material(application_key, application_secret, picture, library):
    """Derive local transport material from the pinned vendor resources."""
    if (not isinstance(application_secret, str)
            or not re.fullmatch(r"[A-Za-z0-9]{32}", application_secret)):
        raise ResourceError("SIGNING_APPLICATION_SECRET")
    secrets = recover_picture_secrets(application_key, picture)
    if not secrets or len(secrets[0]) != 32:
        raise ResourceError("SIGNING_SECRET_LENGTH")
    try:
        secret = secrets[0].decode("ascii")
    except UnicodeError:
        raise ResourceError("SIGNING_SECRET_ENCODING") from None
    if not re.fullmatch(r"[A-Za-z0-9]{32}", secret):
        raise ResourceError("SIGNING_SECRET_FORMAT")
    return _profile_prefix(library) + "_" + secret + "_" + application_secret


def portable_signing_material(identity, dll_folder):
    """Read only the two required, bounded resources from an extracted client."""
    try:
        folder = Path(dll_folder)
        bitmap = folder / "t_s_online.bmp"
        library = folder / "jnimain.dll"
        if (bitmap.is_symlink() or library.is_symlink()
                or not 0x2800 <= bitmap.stat().st_size <= MAX_PICTURE
                or library.stat().st_size != 42496):
            raise ResourceError("SIGNING_RESOURCE_FILES")
        return signing_material(identity["APPKEY"], identity["APPSECRET"],
                                bitmap.read_bytes(), library.read_bytes())
    except (OSError, KeyError, TypeError):
        raise ResourceError("SIGNING_RESOURCE_FILES") from None
