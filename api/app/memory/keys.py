"""Server-side key handling.

JOURNAL_ENCRYPTION_KEY is the one server secret (base64, 32 bytes). Each use gets its own
subkey via HKDF, so compromising one derived key does not expose the others.
"""

import base64
import binascii

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

CHECKPOINT_KEY_INFO = b"grove/checkpoints/v1"


class InvalidKeyError(ValueError):
    pass


def decode_server_key(value: str) -> bytes:
    try:
        raw = base64.urlsafe_b64decode(value.encode())
    except (binascii.Error, ValueError) as exc:
        raise InvalidKeyError("JOURNAL_ENCRYPTION_KEY is not valid base64") from exc
    if len(raw) != 32:
        raise InvalidKeyError("JOURNAL_ENCRYPTION_KEY must decode to 32 bytes")
    return raw


def derive_key(server_key: str, info: bytes) -> bytes:
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info)
    return hkdf.derive(decode_server_key(server_key))
