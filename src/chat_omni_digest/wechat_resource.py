from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path
from typing import Any

from .dat_decoder import detect_dat_version
from .models import Attachment, Conversation, ChatMessage

_HEX32_RE = re.compile(rb"[0-9a-fA-F]{32}")


def _resource_index(blob: bytes | None) -> str | None:
    if not blob:
        return None
    match = _HEX32_RE.search(blob)
    return match.group(0).decode("ascii").lower() if match else None


def _message_int(message: ChatMessage, field: str) -> int | None:
    value = message.raw.get(field)
    if value is None and field == "local_id":
        value = message.id
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _chat_hash(message: ChatMessage) -> str | None:
    table = str(message.raw.get("table") or "")
    if table.startswith("Msg_") and len(table) > 4:
        return table[4:]
    return None


def _image_candidates(account_dir: Path, message: ChatMessage, index: str) -> list[Path]:
    chat_hash = _chat_hash(message)
    month = message.time[:7] if len(message.time) >= 7 else ""
    if not chat_hash or not month:
        return []
    base = account_dir / "msg" / "attach" / chat_hash / month / "Img"
    return [base / f"{index}_t.dat", base / f"{index}.dat"]


def _load_resource_indexes(message_resource_db: Path) -> dict[str, dict[int, str]]:
    conn = sqlite3.connect(str(message_resource_db))
    conn.row_factory = sqlite3.Row
    try:
        table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='MessageResourceInfo'"
        ).fetchone()
        if not table:
            return {"local": {}, "server": {}}

        local: dict[int, str] = {}
        server: dict[int, str] = {}
        rows = conn.execute(
            """
            SELECT message_local_id, message_svr_id, packed_info
            FROM MessageResourceInfo
            WHERE message_local_type = 3
            """
        )
        for row in rows:
            index = _resource_index(row["packed_info"])
            if not index:
                continue
            if row["message_local_id"] is not None:
                local[int(row["message_local_id"])] = index
            if row["message_svr_id"] is not None:
                server[int(row["message_svr_id"])] = index
        return {"local": local, "server": server}
    finally:
        conn.close()


def resolve_wechat_resource_images(
    conversation: Conversation,
    account_dir: str | Path,
    message_resource_db: str | Path,
    copy_dir: str | Path | None = None,
) -> Conversation:
    """Resolve Mac WeChat image resources when the message export lacks md5 XML.

    Mac WeChat 4.x may store image messages as `[图片]` while keeping the local
    resource index in `message_resource.db`. This bridges those rows to the
    local `msg/attach/<chat_hash>/<YYYY-MM>/Img/<index>_t.dat` cache files.
    """
    resource_db = Path(message_resource_db).expanduser()
    if not resource_db.exists():
        return conversation

    account_root = Path(account_dir).expanduser()
    copy_root = Path(copy_dir).expanduser() if copy_dir else None
    if copy_root:
        copy_root.mkdir(parents=True, exist_ok=True)

    indexes = _load_resource_indexes(resource_db)

    for message in conversation.messages:
        if "图片" not in message.type:
            continue

        local_id = _message_int(message, "local_id")
        server_id = _message_int(message, "server_id")
        index = None
        if local_id is not None:
            index = indexes["local"].get(local_id)
        if index is None and server_id is not None:
            index = indexes["server"].get(server_id)
        if not index:
            continue

        candidates = _image_candidates(account_root, message, index)
        existing = next((path for path in candidates if path.exists()), None)
        final_path = existing
        if existing and copy_root:
            target = copy_root / "image" / existing.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copy2(existing, target)
            final_path = target

        if any(a.metadata.get("resource_index") == index for a in message.attachments):
            continue

        metadata: dict[str, Any] = {"resource_index": index}
        if existing:
            try:
                metadata["dat_version"] = detect_dat_version(existing.read_bytes()[:16])
                metadata["file_size"] = existing.stat().st_size
            except OSError:
                pass

        message.attachments.append(
            Attachment(
                kind="image",
                path=str(final_path) if final_path else None,
                filename=f"{index}_t.dat",
                source="message_resource",
                status="resolved" if existing else "candidate-only",
                candidates=[str(path) for path in candidates],
                metadata=metadata,
            )
        )

    return conversation
