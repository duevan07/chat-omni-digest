import json
from pathlib import Path

import pytest

from chat_omni_digest.cli import main
from chat_omni_digest.image_keys import parse_aes_key, parse_xor_key


def _encode_v4_dat(image: bytes, aes_key: bytes, xor_key: int) -> bytes:
    try:
        from Crypto.Cipher import AES  # type: ignore
    except Exception:
        pytest.skip("pycryptodome is not installed")

    aes_plain = image[:9]
    xor_plain = image[9:]
    pad = 16 - (len(aes_plain) % 16)
    encrypted = AES.new(aes_key[:16], AES.MODE_ECB).encrypt(aes_plain + bytes([pad]) * pad)
    xor_data = bytes(byte ^ xor_key for byte in xor_plain)
    header = bytearray(15)
    header[:6] = bytes.fromhex("070856320807")
    header[6:10] = len(aes_plain).to_bytes(4, "little")
    header[10:14] = len(xor_plain).to_bytes(4, "little")
    return bytes(header) + encrypted + xor_data


def test_parse_key_material_accepts_common_forms():
    assert parse_aes_key("0123456789abcdef") == b"0123456789abcdef"
    assert parse_aes_key("30313233343536373839616263646566") == b"0123456789abcdef"
    assert parse_xor_key("0x35") == 0x35
    assert parse_xor_key("53") == 53


def test_image_keys_doctor_decodes_without_printing_keys(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    aes_key = "0123456789abcdef"
    xor_key = "0x35"
    dat_path = tmp_path / "sample.dat"
    dat_path.write_bytes(_encode_v4_dat(bytes.fromhex("ffd8ff") + b"fake-jpeg-body", aes_key.encode(), 0x35))
    output_dir = tmp_path / "decoded"
    config_path = tmp_path / "keys.json"

    rc = main(
        [
            "image-keys",
            "doctor",
            "--dat",
            str(dat_path),
            "--image-aes-key",
            aes_key,
            "--image-xor-key",
            xor_key,
            "--output-dir",
            str(output_dir),
            "--image-key-config",
            str(config_path),
            "--save",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["decoded"] == 1
    assert payload["has_aes_key"] is True
    assert payload["has_xor_key"] is True
    assert aes_key not in json.dumps(payload)
    assert xor_key not in json.dumps(payload)
    assert (output_dir / "sample.jpg").exists()
    assert config_path.exists()


def test_image_keys_doctor_merges_arguments_with_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    aes_key = "0123456789abcdef"
    dat_path = tmp_path / "sample.dat"
    dat_path.write_bytes(_encode_v4_dat(bytes.fromhex("ffd8ff") + b"fake-jpeg-body", aes_key.encode(), 0x35))
    config_path = tmp_path / "keys.json"
    config_path.write_text(
        json.dumps({"wechat_image": {"imageXorKey": "0x35"}}, ensure_ascii=False),
        encoding="utf-8",
    )

    rc = main(
        [
            "image-keys",
            "doctor",
            "--dat",
            str(dat_path),
            "--image-aes-key",
            aes_key,
            "--image-key-config",
            str(config_path),
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["decoded"] == 1


def test_decode_images_updates_conversation_path(tmp_path: Path):
    aes_key = "0123456789abcdef"
    dat_path = tmp_path / "sample.dat"
    dat_path.write_bytes(_encode_v4_dat(bytes.fromhex("ffd8ff") + b"fake-jpeg-body", aes_key.encode(), 0x35))
    source = tmp_path / "chat.json"
    source.write_text(
        json.dumps(
            {
                "group": {"name": "Demo"},
                "messages": [
                    {
                        "id": "1",
                        "time": "2026-06-25 10:00:00",
                        "sender": "Alice",
                        "type": "图片",
                        "content": "[图片]",
                        "attachments": [{"kind": "image", "path": str(dat_path), "status": "resolved"}],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "decoded.json"
    decoded_dir = tmp_path / "decoded"

    rc = main(
        [
            "decode-images",
            str(source),
            str(output),
            "--output-dir",
            str(decoded_dir),
            "--image-aes-key",
            aes_key,
            "--image-xor-key",
            "0x35",
        ]
    )

    assert rc == 0
    data = json.loads(output.read_text(encoding="utf-8"))
    attachment = data["messages"][0]["attachments"][0]
    assert attachment["status"] == "decoded"
    assert attachment["path"].endswith(".jpg")
    assert Path(attachment["path"]).exists()
