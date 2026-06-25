import pytest

from chat_omni_digest.dat_decoder import decode_dat_bytes, decode_xor_dat


def test_decode_xor_dat_jpeg():
    raw = bytes.fromhex("ffd8ff") + b"hello"
    key = 0x42
    encoded = bytes(b ^ key for b in raw)
    decoded = decode_xor_dat(encoded)
    assert decoded is not None
    data, ext = decoded
    assert ext == ".jpg"
    assert data == raw


def _encode_v4_dat(image: bytes, aes_key: bytes, xor_key: int) -> bytes:
    try:
        from Crypto.Cipher import AES  # type: ignore
    except Exception:
        pytest.skip("pycryptodome is not installed")

    aes_plain = image[:7]
    xor_plain = image[7:]
    pad = 16 - (len(aes_plain) % 16)
    encrypted = AES.new(aes_key[:16], AES.MODE_ECB).encrypt(aes_plain + bytes([pad]) * pad)
    xor_data = bytes(byte ^ xor_key for byte in xor_plain)
    header = bytearray(15)
    header[:6] = bytes.fromhex("070856320807")
    header[6:10] = len(aes_plain).to_bytes(4, "little")
    header[10:14] = len(xor_plain).to_bytes(4, "little")
    return bytes(header) + encrypted + xor_data


def test_decode_v4_dat_jpeg_with_keys():
    image = bytes.fromhex("ffd8ff") + b"fake-jpeg-body"
    aes_key = b"0123456789abcdef"
    xor_key = 0x35
    encoded = _encode_v4_dat(image, aes_key, xor_key)

    decoded = decode_dat_bytes(encoded, aes_key=aes_key, xor_key=xor_key)

    assert decoded is not None
    data, ext, version = decoded
    assert data == image
    assert ext == ".jpg"
    assert version == 2


def test_decode_v4_dat_without_keys_returns_none():
    image = bytes.fromhex("ffd8ff") + b"fake-jpeg-body"
    encoded = _encode_v4_dat(image, b"0123456789abcdef", 0x35)

    assert decode_dat_bytes(encoded) is None
