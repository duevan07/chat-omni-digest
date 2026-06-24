from __future__ import annotations

import json
from pathlib import Path

from .models import Conversation


def load_conversation(path: str | Path) -> Conversation:
    source = Path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(data, list):
        data = {"name": source.stem, "messages": data}
    if not isinstance(data, dict):
        raise ValueError(f"Unsupported chat JSON shape in {source}")
    return Conversation.from_dict(data)


def save_conversation(conversation: Conversation, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(conversation.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

