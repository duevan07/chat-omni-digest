from chat_omni_digest.dat_decoder import decode_xor_dat


def test_decode_xor_dat_jpeg():
    raw = bytes.fromhex("ffd8ff") + b"hello"
    key = 0x42
    encoded = bytes(b ^ key for b in raw)
    decoded = decode_xor_dat(encoded)
    assert decoded is not None
    data, ext = decoded
    assert ext == ".jpg"
    assert data == raw

