from __future__ import annotations

from collections import Counter
from pathlib import Path

from .models import Conversation


def _display_content(content: str) -> str:
    value = (content or "").replace("\n", " ").replace("\r", " ")
    if not value:
        return ""
    weird = sum(1 for char in value if (ord(char) < 32 and char not in "\t ") or char == "\ufffd")
    if weird / max(len(value), 1) > 0.03:
        return "[链接/文件/小程序内容未解码]"
    if len(value) > 160:
        return value[:160] + "..."
    return value


def build_markdown_report(conversation: Conversation) -> str:
    messages = conversation.messages
    type_counts = Counter(m.type for m in messages)
    sender_counts = Counter(m.sender for m in messages if m.sender)
    attachments = [a for m in messages for a in m.attachments]
    resolved = [a for a in attachments if a.status == "resolved"]
    unresolved = [a for a in attachments if a.status != "resolved"]

    lines = [
        f"# {conversation.name} 聊天记录解析报告",
        "",
        "## 概览",
        "",
        f"- 消息数：{len(messages)}",
        f"- 附件数：{len(attachments)}",
        f"- 已解析附件：{len(resolved)}",
        f"- 未解析附件：{len(unresolved)}",
        "",
        "## 消息类型",
        "",
    ]
    for name, count in type_counts.most_common():
        lines.append(f"- {name or '未知'}：{count}")
    lines.extend(["", "## 发言排行", ""])
    for name, count in sender_counts.most_common(15):
        lines.append(f"- {name}：{count}")

    lines.extend(["", "## 附件摘要", ""])
    for attachment in attachments[:100]:
        title = attachment.filename or attachment.md5 or attachment.kind
        lines.append(f"### {attachment.kind}: {title}")
        lines.append("")
        lines.append(f"- 状态：{attachment.status}")
        if attachment.path:
            lines.append(f"- 路径：`{attachment.path}`")
        if attachment.summary:
            excerpt = attachment.summary.strip().replace("\n", "\n  ")
            lines.append(f"- 内容摘录：\n  {excerpt}")
        lines.append("")

    lines.extend(["## 最近消息抽样", ""])
    for message in messages[-30:]:
        content = _display_content(message.content)
        lines.append(f"- `{message.time}` **{message.sender}** [{message.type}] {content}")
    lines.append("")
    return "\n".join(lines)


def write_markdown_report(conversation: Conversation, output: str | Path) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown_report(conversation), encoding="utf-8")


def write_pdf_report(conversation: Conversation, output: str | Path) -> None:
    try:
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore
        from reportlab.lib.units import mm  # type: ignore
        from reportlab.pdfbase import pdfmetrics  # type: ignore
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont  # type: ignore
        from reportlab.pdfbase.ttfonts import TTFont  # type: ignore
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install chat-omni-digest[pdf] to generate PDF reports") from exc

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)

    font_name = "Helvetica"
    for candidate in (
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ):
        if Path(candidate).exists():
            try:
                pdfmetrics.registerFont(TTFont("ChatDigestCN", candidate, subfontIndex=0))
                font_name = "ChatDigestCN"
                break
            except Exception:
                continue
    if font_name == "Helvetica":
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            font_name = "STSong-Light"
        except Exception:
            pass

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "BodyCN",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10.5,
        leading=16,
        wordWrap="CJK",
    )
    title = ParagraphStyle(
        "TitleCN",
        parent=body,
        fontSize=18,
        leading=24,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "H2CN",
        parent=body,
        fontSize=13,
        leading=19,
        spaceBefore=8,
        spaceAfter=4,
    )

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{conversation.name} 聊天记录解析报告",
    )
    story = []
    for line in build_markdown_report(conversation).splitlines():
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if safe.startswith("# "):
            story.append(Paragraph(safe[2:], title))
        elif safe.startswith("## "):
            story.append(Paragraph(safe[3:], h2))
        elif safe.strip():
            story.append(Paragraph(safe, body))
        else:
            story.append(Spacer(1, 4))
    doc.build(story)
