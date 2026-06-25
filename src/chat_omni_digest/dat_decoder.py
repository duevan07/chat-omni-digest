from __future__ import annotations

from pathlib import Path

MAGIC_HEADERS = {
    ".jpg": bytes.fromhex("ffd8ff"),
    ".png": b"\x89PNG",
    ".gif": b"GIF8",
}
DEFAULT_V1_AES_KEY = b"cfcd208495d565ef"


def detect_image_extension(data: bytes) -> str | None:
    if data.startswith(bytes.fromhex("ffd8ff")):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return None


def detect_dat_version(data: bytes) -> int:
    if len(data) < 6:
        return 0
    if data[:6] == bytes([0x07, 0x08, 0x56, 0x31, 0x08, 0x07]):
        return 1
    if data[:6] == bytes([0x07, 0x08, 0x56, 0x32, 0x08, 0x07]):
        return 2
    return 0


def decode_xor_dat(data: bytes) -> tuple[bytes, str] | None:
    """Decode classic WeChat image .dat files by inferring an XOR key."""
    if not data:
        return None
    for ext, magic in MAGIC_HEADERS.items():
        key = data[0] ^ magic[0]
        decoded_prefix = bytes(b ^ key for b in data[: len(magic)])
        if decoded_prefix == magic:
            decoded = bytes(b ^ key for b in data)
            return decoded, ext
    return None


def decode_v4_dat(data: bytes, xor_key: int, aes_key: bytes) -> bytes:
    """Decode newer mixed AES/XOR dat files when pycryptodome is installed."""
    try:
        from Crypto.Cipher import AES  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install chat-omni-digest[media] to decode v4 dat files") from exc

    if len(data) < 0x0F:
        raise ValueError("dat file is too small")
    header = data[:0x0F]
    payload = data[0x0F:]
    aes_size = int.from_bytes(header[6:10], "little", signed=False)
    xor_size = int.from_bytes(header[10:14], "little", signed=False)
    aligned = aes_size + ((16 - (aes_size % 16)) % 16)
    if aligned > len(payload):
        raise ValueError("invalid dat aes segment length")
    aes_data = payload[:aligned]
    remaining = payload[aligned:]
    chunks: list[bytes] = []
    if aes_data:
        decrypted = AES.new(aes_key[:16], AES.MODE_ECB).decrypt(aes_data)
        pad = decrypted[-1]
        if pad <= 0 or pad > 16:
            raise ValueError("invalid PKCS7 padding")
        chunks.append(decrypted[:-pad])
    if xor_size:
        raw_len = len(remaining) - xor_size
        if raw_len < 0:
            raise ValueError("invalid dat xor segment length")
        chunks.append(remaining[:raw_len])
        chunks.append(bytes(b ^ xor_key for b in remaining[raw_len:]))
    else:
        chunks.append(remaining)
    return b"".join(chunks)


def decode_dat_bytes(
    data: bytes,
    *,
    xor_key: int | None = None,
    aes_key: bytes | None = None,
) -> tuple[bytes, str, int] | None:
    """Decode a WeChat image .dat payload.

    Returns decoded bytes, image extension, and detected dat version. No secret
    material is returned to callers.
    """
    version = detect_dat_version(data)
    classic = decode_xor_dat(data)
    if classic:
        decoded, ext = classic
        return decoded, ext, version

    if version not in {1, 2}:
        return None

    header = data[:0x0F]
    xor_size = int.from_bytes(header[10:14], "little", signed=False) if len(header) >= 14 else 0
    effective_aes_key = aes_key
    if version == 1 and effective_aes_key is None:
        effective_aes_key = DEFAULT_V1_AES_KEY
    if effective_aes_key is None:
        return None
    if xor_size and xor_key is None:
        return None

    decoded = decode_v4_dat(data, xor_key or 0, effective_aes_key)
    ext = detect_image_extension(decoded)
    if not ext:
        return None
    return decoded, ext, version


def decode_dat_file(
    path: str | Path,
    output_dir: str | Path,
    *,
    xor_key: int | None = None,
    aes_key: bytes | None = None,
) -> Path | None:
    source = Path(path)
    data = source.read_bytes()
    decoded = decode_dat_bytes(data, xor_key=xor_key, aes_key=aes_key)
    if not decoded:
        return None
    decoded_data, ext, _version = decoded
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"{source.stem}{ext}"
    target.write_bytes(decoded_data)
    return target
