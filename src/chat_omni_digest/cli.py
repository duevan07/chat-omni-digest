from __future__ import annotations

import argparse
from pathlib import Path

from .attachments import enrich_attachments
from .io import load_conversation, save_conversation
from .report import write_markdown_report, write_pdf_report
from .resolver import resolve_conversation_media
from .wechat_resource import resolve_wechat_resource_images


def _cmd_normalize(args: argparse.Namespace) -> int:
    conversation = load_conversation(args.input)
    save_conversation(conversation, args.output)
    return 0


def _cmd_resolve_media(args: argparse.Namespace) -> int:
    conversation = load_conversation(args.input)
    resolve_conversation_media(
        conversation,
        account_dir=args.account_dir,
        hardlink_db=args.hardlink_db,
        copy_dir=args.copy_media,
    )
    if args.message_resource_db:
        resolve_wechat_resource_images(
            conversation,
            account_dir=args.account_dir,
            message_resource_db=args.message_resource_db,
            copy_dir=args.copy_media,
        )
    save_conversation(conversation, args.output)
    return 0


def _cmd_enrich(args: argparse.Namespace) -> int:
    conversation = load_conversation(args.input)
    enrich_attachments(conversation, max_chars=args.max_chars)
    save_conversation(conversation, args.output)
    return 0


def _cmd_summarize(args: argparse.Namespace) -> int:
    conversation = load_conversation(args.input)
    write_markdown_report(conversation, args.output)
    if args.pdf:
        write_pdf_report(conversation, args.pdf)
    return 0


def _cmd_pipeline(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    normalized = output_dir / "conversation.normalized.json"
    resolved = output_dir / "conversation.resolved.json"
    enriched = output_dir / "conversation.enriched.json"
    report = output_dir / "report.md"
    pdf_report = output_dir / "report.pdf"

    conversation = load_conversation(args.input)
    save_conversation(conversation, normalized)
    resolve_conversation_media(
        conversation,
        account_dir=args.account_dir,
        hardlink_db=args.hardlink_db,
        copy_dir=output_dir / "media" if args.copy_media else None,
    )
    if args.message_resource_db:
        resolve_wechat_resource_images(
            conversation,
            account_dir=args.account_dir,
            message_resource_db=args.message_resource_db,
            copy_dir=output_dir / "media" if args.copy_media else None,
        )
    save_conversation(conversation, resolved)
    enrich_attachments(conversation, max_chars=args.max_chars)
    save_conversation(conversation, enriched)
    write_markdown_report(conversation, report)
    if args.pdf:
        write_pdf_report(conversation, pdf_report)
    print(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chatdig", description="Local-first multimodal chat digest pipeline.")
    sub = parser.add_subparsers(dest="command", required=True)

    normalize = sub.add_parser("normalize", help="Normalize exported chat JSON into the chatdig schema.")
    normalize.add_argument("input")
    normalize.add_argument("output")
    normalize.set_defaults(func=_cmd_normalize)

    resolve = sub.add_parser("resolve-media", help="Resolve image/video/file attachments through hardlink.db.")
    resolve.add_argument("input")
    resolve.add_argument("output")
    resolve.add_argument("--account-dir", required=True, help="WeChat account directory containing msg/FileStorage files.")
    resolve.add_argument("--hardlink-db", help="Path to hardlink.db. Auto-detected from account-dir if omitted.")
    resolve.add_argument("--message-resource-db", help="Optional message_resource.db for Mac WeChat image resource indexes.")
    resolve.add_argument("--copy-media", help="Optional directory to copy resolved media into.")
    resolve.set_defaults(func=_cmd_resolve_media)

    enrich = sub.add_parser("enrich", help="Extract text from resolved local file attachments.")
    enrich.add_argument("input")
    enrich.add_argument("output")
    enrich.add_argument("--max-chars", type=int, default=4000)
    enrich.set_defaults(func=_cmd_enrich)

    summarize = sub.add_parser("summarize", help="Write a Markdown digest report.")
    summarize.add_argument("input")
    summarize.add_argument("output")
    summarize.add_argument("--pdf", help="Optional PDF report output path.")
    summarize.set_defaults(func=_cmd_summarize)

    pipeline = sub.add_parser("pipeline", help="Run normalize, media resolve, file enrich, and Markdown report.")
    pipeline.add_argument("input")
    pipeline.add_argument("--output-dir", required=True)
    pipeline.add_argument("--account-dir", required=True)
    pipeline.add_argument("--hardlink-db")
    pipeline.add_argument("--message-resource-db")
    pipeline.add_argument("--copy-media", action="store_true")
    pipeline.add_argument("--max-chars", type=int, default=4000)
    pipeline.add_argument("--pdf", action="store_true", help="Also write report.pdf in the output directory.")
    pipeline.set_defaults(func=_cmd_pipeline)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
