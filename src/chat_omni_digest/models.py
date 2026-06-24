from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Attachment:
    kind: str
    path: str | None = None
    md5: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    source: str | None = None
    status: str = "unresolved"
    candidates: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    summary: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Attachment":
        return cls(
            kind=str(data.get("kind") or "file"),
            path=data.get("path"),
            md5=data.get("md5"),
            filename=data.get("filename"),
            mime_type=data.get("mime_type"),
            source=data.get("source"),
            status=str(data.get("status") or "unresolved"),
            candidates=list(data.get("candidates") or []),
            metadata=dict(data.get("metadata") or {}),
            summary=data.get("summary"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChatMessage:
    id: str
    time: str
    sender: str
    type: str
    content: str = ""
    sender_username: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    attachments: list[Attachment] = field(default_factory=list)
    annotations: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatMessage":
        msg_id = (
            data.get("id")
            or data.get("server_id")
            or data.get("local_id")
            or data.get("msg_id")
            or data.get("MsgSvrID")
            or ""
        )
        attachments = [
            Attachment.from_dict(item)
            for item in data.get("attachments", [])
            if isinstance(item, dict)
        ]
        return cls(
            id=str(msg_id),
            time=str(data.get("time") or data.get("timestamp") or ""),
            sender=str(data.get("sender") or data.get("from") or ""),
            sender_username=data.get("sender_username"),
            type=str(data.get("type") or data.get("msg_type") or ""),
            content=str(data.get("content") or data.get("message_content") or ""),
            raw=dict(data.get("raw") or data),
            attachments=attachments,
            annotations=dict(data.get("annotations") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["attachments"] = [item.to_dict() for item in self.attachments]
        return data


@dataclass
class Conversation:
    name: str
    username: str | None = None
    range: dict[str, Any] = field(default_factory=dict)
    messages: list[ChatMessage] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Conversation":
        group = data.get("group") if isinstance(data.get("group"), dict) else {}
        messages = [
            ChatMessage.from_dict(item)
            for item in data.get("messages", [])
            if isinstance(item, dict)
        ]
        return cls(
            name=str(group.get("name") or data.get("name") or "chat"),
            username=group.get("username") or data.get("username"),
            range=dict(data.get("range") or {}),
            messages=messages,
            metadata={
                k: v
                for k, v in data.items()
                if k not in {"group", "name", "username", "range", "messages"}
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "group": {"name": self.name, "username": self.username},
            "range": self.range,
            "metadata": self.metadata,
            "messages": [item.to_dict() for item in self.messages],
        }

