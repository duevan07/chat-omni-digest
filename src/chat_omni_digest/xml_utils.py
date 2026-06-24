from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Any

_HEX32 = r"[0-9a-fA-F]{32}"


def _clean_xml(content: str) -> str:
    value = (content or "").strip()
    if value.startswith("null:"):
        value = value[5:].strip()
    return html.unescape(value)


def _first_regex(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return match.group(1)
    return None


def _text_from_tag(root: ET.Element, tag: str) -> str | None:
    node = root.find(f".//{tag}")
    if node is not None and node.text:
        return node.text.strip()
    return None


def extract_media_fields(content: str, kind_hint: str | None = None) -> dict[str, Any]:
    """Extract md5, file metadata, URL and title from WeChat XML-ish content.

    WeChat message payloads are often malformed XML. This function first tries
    XML parsing, then falls back to regex so duplicate attributes and prefixed
    blobs do not make media lookup impossible.
    """
    value = _clean_xml(content)
    fields: dict[str, Any] = {}

    try:
        root = ET.fromstring(value)
        if kind_hint == "video":
            video = root.find(".//videomsg")
            if video is not None:
                fields["md5"] = video.attrib.get("md5") or fields.get("md5")
        else:
            image = root.find(".//img")
            if image is not None:
                fields["md5"] = image.attrib.get("md5") or fields.get("md5")
        appattach = root.find(".//appattach")
        if appattach is not None:
            for tag in ("filemd5", "md5", "attachid", "fileext", "totallen"):
                text = _text_from_tag(appattach, tag)
                if text:
                    fields[tag] = text
        for tag in ("title", "des", "url", "type"):
            text = _text_from_tag(root, tag)
            if text:
                fields[tag] = text
    except ET.ParseError:
        pass

    fields.setdefault(
        "md5",
        _first_regex(
            [
                rf"<img\b[^>]*\bmd5=['\"]({_HEX32})['\"]",
                rf"<videomsg\b[^>]*\bmd5=['\"]({_HEX32})['\"]",
                rf"<filemd5>\s*({_HEX32})\s*</filemd5>",
                rf"<md5>\s*({_HEX32})\s*</md5>",
                rf"\bmd5=['\"]({_HEX32})['\"]",
            ],
            value,
        ),
    )
    for key, patterns in {
        "filemd5": [rf"<filemd5>\s*({_HEX32})\s*</filemd5>"],
        "attachid": [r"<attachid>\s*([^<]+?)\s*</attachid>"],
        "title": [r"<title>\s*([^<]+?)\s*</title>"],
        "des": [r"<des>\s*([^<]+?)\s*</des>"],
        "url": [r"<url>\s*(https?://[^<]+?)\s*</url>"],
        "fileext": [r"<fileext>\s*([^<]+?)\s*</fileext>"],
        "totallen": [r"<totallen>\s*([^<]+?)\s*</totallen>"],
    }.items():
        fields.setdefault(key, _first_regex(patterns, value))

    if not fields.get("md5") and fields.get("filemd5"):
        fields["md5"] = fields["filemd5"]
    return {k: html.unescape(str(v)).strip() for k, v in fields.items() if v}


def infer_kind(message_type: str, content: str = "") -> str | None:
    value = f"{message_type} {content}".lower()
    if "文件" in message_type or "<appattach" in value:
        return "file"
    if "图片" in message_type or "<img" in value:
        return "image"
    if "视频" in message_type or "<videomsg" in value:
        return "video"
    if "语音" in message_type:
        return "voice"
    if "链接" in message_type or "<url>" in value or "mp.weixin.qq.com" in value:
        return "article"
    return None
