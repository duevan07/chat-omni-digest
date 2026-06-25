from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dat_decoder import decode_dat_bytes, detect_dat_version
from .io import load_conversation
from .models import Conversation

DEFAULT_IMAGE_KEY_CONFIG = Path("~/.config/chat-omni-digest/image-keys.json").expanduser()


@dataclass(frozen=True)
class ImageKeyMaterial:
    aes_key: bytes | None
    xor_key: int | None
    source: str
    raw_aes_key: str | None = None
    raw_xor_key: str | None = None

    @property
    def complete(self) -> bool:
        return self.aes_key is not None and self.xor_key is not None


@dataclass
class DatProbeResult:
    path: str
    version: int
    status: str
    extension: str | None = None
    decoded_path: str | None = None
    error: str | None = None


def parse_aes_key(value: str | None) -> bytes | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    compact_hex = "".join(ch for ch in text if ch not in " :-_")
    if len(compact_hex) % 2 == 0 and len(compact_hex) >= 32:
        try:
            raw = bytes.fromhex(compact_hex)
            if len(raw) >= 16:
                return raw
        except ValueError:
            pass

    try:
        raw = base64.b64decode(text, validate=True)
        if len(raw) >= 16:
            return raw
    except Exception:
        pass

    raw = text.encode("utf-8")
    if len(raw) >= 16:
        return raw
    return None


def parse_xor_key(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 255 else None
    text = value.strip().lower()
    if not text:
        return None
    try:
        if text.startswith("0x"):
            number = int(text, 16)
        elif any(ch in "abcdef" for ch in text):
            number = int(text, 16)
        else:
            number = int(text, 10)
    except ValueError:
        return None
    return number if 0 <= number <= 255 else None


def _pick_key_fields(data: dict[str, Any]) -> tuple[str | None, str | int | None]:
    containers: list[dict[str, Any]] = [data]
    for key in ("image", "wechat_image", "wechat", "keys"):
        value = data.get(key)
        if isinstance(value, dict):
            containers.append(value)

    aes_names = ("imageAesKey", "image_aes_key", "aesKey", "aes_key")
    xor_names = ("imageXorKey", "image_xor_key", "xorKey", "xor_key")
    aes_value: str | None = None
    xor_value: str | int | None = None
    for item in containers:
        if aes_value is None:
            aes_value = next((str(item[name]) for name in aes_names if item.get(name) is not None), None)
        if xor_value is None:
            xor_value = next((item[name] for name in xor_names if item.get(name) is not None), None)
    return aes_value, xor_value


def _load_config_key_material(config_path: str | Path | None = None) -> ImageKeyMaterial:
    path = Path(config_path).expanduser() if config_path else DEFAULT_IMAGE_KEY_CONFIG
    if not path.exists():
        return ImageKeyMaterial(aes_key=None, xor_key=None, source="missing-config")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ImageKeyMaterial(aes_key=None, xor_key=None, source="invalid-config")
    if not isinstance(data, dict):
        return ImageKeyMaterial(aes_key=None, xor_key=None, source="invalid-config")
    raw_aes, raw_xor = _pick_key_fields(data)
    return ImageKeyMaterial(
        aes_key=parse_aes_key(raw_aes),
        xor_key=parse_xor_key(raw_xor),
        source=str(path),
        raw_aes_key=raw_aes,
        raw_xor_key=str(raw_xor) if raw_xor is not None else None,
    )


def load_key_material(config_path: str | Path | None = None) -> ImageKeyMaterial:
    config = _load_config_key_material(config_path)
    env_aes = os.environ.get("CHATDIG_IMAGE_AES_KEY") or os.environ.get("WECHAT_IMAGE_AES_KEY")
    env_xor = os.environ.get("CHATDIG_IMAGE_XOR_KEY") or os.environ.get("WECHAT_IMAGE_XOR_KEY")
    if not env_aes and not env_xor:
        return config

    raw_aes = env_aes or config.raw_aes_key
    raw_xor = env_xor or config.raw_xor_key
    return ImageKeyMaterial(
        aes_key=parse_aes_key(raw_aes),
        xor_key=parse_xor_key(raw_xor),
        source="environment" if config.source == "missing-config" else f"environment+{config.source}",
        raw_aes_key=raw_aes,
        raw_xor_key=raw_xor,
    )


def save_key_material(
    key_material: ImageKeyMaterial,
    config_path: str | Path | None = None,
) -> Path:
    if not key_material.raw_aes_key or key_material.raw_xor_key is None:
        raise ValueError("only user-provided key strings can be saved")
    path = Path(config_path).expanduser() if config_path else DEFAULT_IMAGE_KEY_CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "wechat_image": {
            "imageAesKey": key_material.raw_aes_key,
            "imageXorKey": key_material.raw_xor_key,
        },
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def collect_dat_paths(
    *,
    dat_paths: list[str] | None = None,
    conversation_path: str | Path | None = None,
) -> list[Path]:
    paths: list[Path] = []
    for item in dat_paths or []:
        path = Path(item).expanduser()
        if path.is_dir():
            paths.extend(sorted(path.rglob("*.dat")))
        else:
            paths.append(path)

    if conversation_path:
        conversation = load_conversation(conversation_path)
        for message in conversation.messages:
            for attachment in message.attachments:
                if attachment.kind != "image":
                    continue
                attachment_path = Path(attachment.path).expanduser() if attachment.path else None
                if attachment_path and attachment_path.suffix.lower() == ".dat" and attachment_path.exists():
                    paths.append(attachment_path)
                    continue
                existing_candidates = [
                    Path(candidate).expanduser()
                    for candidate in attachment.candidates
                    if candidate and Path(candidate).expanduser().suffix.lower() == ".dat" and Path(candidate).expanduser().exists()
                ]
                paths.extend(existing_candidates)

    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve() if path.exists() else path
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def probe_dat_files(
    paths: list[Path],
    key_material: ImageKeyMaterial,
    *,
    output_dir: str | Path | None = None,
) -> list[DatProbeResult]:
    output = Path(output_dir).expanduser() if output_dir else None
    if output:
        output.mkdir(parents=True, exist_ok=True)

    results: list[DatProbeResult] = []
    for path in paths:
        try:
            data = path.read_bytes()
        except OSError as exc:
            results.append(DatProbeResult(path=str(path), version=0, status="missing", error=exc.__class__.__name__))
            continue

        version = detect_dat_version(data)
        try:
            decoded = decode_dat_bytes(data, xor_key=key_material.xor_key, aes_key=key_material.aes_key)
        except Exception as exc:
            results.append(
                DatProbeResult(path=str(path), version=version, status="failed", error=exc.__class__.__name__)
            )
            continue

        if not decoded:
            status = "needs-key" if version in {1, 2} and not key_material.complete else "unrecognized"
            results.append(DatProbeResult(path=str(path), version=version, status=status))
            continue

        decoded_data, ext, decoded_version = decoded
        decoded_path = None
        if output:
            target = output / f"{path.stem}{ext}"
            target.write_bytes(decoded_data)
            decoded_path = str(target)
        results.append(
            DatProbeResult(
                path=str(path),
                version=decoded_version,
                status="decoded",
                extension=ext,
                decoded_path=decoded_path,
            )
        )
    return results


def decode_conversation_images(
    conversation: Conversation,
    key_material: ImageKeyMaterial,
    output_dir: str | Path,
) -> Conversation:
    output = Path(output_dir).expanduser()
    output.mkdir(parents=True, exist_ok=True)

    for message in conversation.messages:
        for attachment in message.attachments:
            if attachment.kind != "image" or not attachment.path:
                continue
            source = Path(attachment.path).expanduser()
            if not source.exists():
                attachment.metadata["decode_status"] = "missing"
                continue
            try:
                data = source.read_bytes()
                decoded = decode_dat_bytes(data, xor_key=key_material.xor_key, aes_key=key_material.aes_key)
            except Exception as exc:
                attachment.metadata["decode_status"] = "failed"
                attachment.metadata["decode_error"] = exc.__class__.__name__
                continue
            if not decoded:
                attachment.metadata["decode_status"] = (
                    "needs-key" if detect_dat_version(data) in {1, 2} and not key_material.complete else "unrecognized"
                )
                continue

            decoded_data, ext, version = decoded
            target = output / f"{source.stem}{ext}"
            target.write_bytes(decoded_data)
            attachment.metadata["source_dat_path"] = str(source)
            attachment.metadata["decoded_path"] = str(target)
            attachment.metadata["decoded_ext"] = ext
            attachment.metadata["decoded_dat_version"] = version
            attachment.metadata["decode_status"] = "decoded"
            attachment.path = str(target)
            attachment.status = "decoded"
    return conversation


def summarize_probe_results(results: list[DatProbeResult]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    versions: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
        versions[str(result.version)] = versions.get(str(result.version), 0) + 1
    return {
        "checked": len(results),
        "status_counts": counts,
        "dat_versions": versions,
        "decoded": counts.get("decoded", 0),
    }
