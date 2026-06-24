from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path

from .hardlink import HardlinkResolver
from .models import Attachment, Conversation
from .xml_utils import extract_media_fields, infer_kind


def resolve_conversation_media(
    conversation: Conversation,
    account_dir: str | Path,
    hardlink_db: str | Path | None = None,
    copy_dir: str | Path | None = None,
) -> Conversation:
    copy_root = Path(copy_dir).expanduser() if copy_dir else None
    if copy_root:
        copy_root.mkdir(parents=True, exist_ok=True)

    with HardlinkResolver(account_dir, hardlink_db) as resolver:
        for message in conversation.messages:
            kind = infer_kind(message.type, message.content)
            if kind == "article" or kind == "voice" or not kind:
                continue
            fields = extract_media_fields(message.content, kind_hint=kind)
            md5 = fields.get("md5")
            if not md5:
                continue
            lookup_kind = "file" if kind == "file" else kind
            resolved = resolver.resolve(lookup_kind, md5)
            if not resolved:
                continue
            path = resolved.path
            final_path: Path | None = path
            if path and copy_root:
                suffix = path.suffix or ""
                name = resolved.filename or f"{message.id or md5}{suffix}"
                target = copy_root / lookup_kind / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    shutil.copy2(path, target)
                final_path = target
            mime_type, _ = mimetypes.guess_type(str(final_path or resolved.filename or ""))
            message.attachments.append(
                Attachment(
                    kind=lookup_kind,
                    path=str(final_path) if final_path else None,
                    md5=md5,
                    filename=resolved.filename or fields.get("title"),
                    mime_type=mime_type,
                    source="hardlink",
                    status=resolved.status,
                    candidates=[str(item) for item in resolved.candidates],
                    metadata={**fields, **resolved.metadata},
                )
            )
    return conversation

