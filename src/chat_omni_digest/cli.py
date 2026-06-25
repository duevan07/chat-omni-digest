from __future__ import annotations

import argparse
import json
from pathlib import Path

from .attachments import enrich_attachments
from .image_keys import (
    ImageKeyMaterial,
    collect_dat_paths,
    decode_conversation_images,
    load_key_material,
    parse_aes_key,
    parse_xor_key,
    probe_dat_files,
    save_key_material,
    summarize_probe_results,
)
from .io import load_conversation, save_conversation
from .report import write_markdown_report, write_pdf_report
from .resolver import resolve_conversation_media
from .wechat_resource import resolve_wechat_resource_images


def _key_material_from_args(args: argparse.Namespace) -> ImageKeyMaterial:
    base = load_key_material(getattr(args, "image_key_config", None))
    if getattr(args, "image_aes_key", None) or getattr(args, "image_xor_key", None):
        raw_aes = args.image_aes_key or base.raw_aes_key
        raw_xor = args.image_xor_key or base.raw_xor_key
        return ImageKeyMaterial(
            aes_key=parse_aes_key(raw_aes),
            xor_key=parse_xor_key(raw_xor),
            source="arguments" if base.source == "missing-config" else f"arguments+{base.source}",
            raw_aes_key=raw_aes,
            raw_xor_key=raw_xor,
        )
    return base


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


def _cmd_decode_images(args: argparse.Namespace) -> int:
    conversation = load_conversation(args.input)
    key_material = _key_material_from_args(args)
    decode_conversation_images(conversation, key_material, args.output_dir)
    save_conversation(conversation, args.output)
    return 0


def _cmd_image_keys_doctor(args: argparse.Namespace) -> int:
    paths = collect_dat_paths(dat_paths=args.dat, conversation_path=args.conversation)
    key_material = _key_material_from_args(args)
    results = probe_dat_files(paths, key_material, output_dir=args.output_dir)
    summary = summarize_probe_results(results)
    saved_config = None
    if args.save and summary["decoded"] > 0:
        saved_config = str(save_key_material(key_material, args.image_key_config))

    payload = {
        **summary,
        "key_source": key_material.source,
        "has_aes_key": key_material.aes_key is not None,
        "has_xor_key": key_material.xor_key is not None,
        "saved_config": saved_config,
        "results": [item.__dict__ for item in results],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print("Image key doctor")
    print(f"- checked: {summary['checked']}")
    print(f"- dat versions: {summary['dat_versions']}")
    print(f"- status: {summary['status_counts']}")
    print(f"- key source: {key_material.source}")
    print(f"- has aes key: {'yes' if key_material.aes_key is not None else 'no'}")
    print(f"- has xor key: {'yes' if key_material.xor_key is not None else 'no'}")
    if args.output_dir:
        print(f"- decoded output: {args.output_dir}")
    if saved_config:
        print(f"- saved config: {saved_config}")
    if args.save and not saved_config:
        print("- saved config: skipped because no image decoded successfully")
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
    if args.decode_images:
        key_material = _key_material_from_args(args)
        decode_conversation_images(conversation, key_material, output_dir / "media" / "decoded-image")
        decoded = output_dir / "conversation.decoded.json"
        save_conversation(conversation, decoded)
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

    decode_images = sub.add_parser("decode-images", help="Decode resolved WeChat image .dat attachments.")
    decode_images.add_argument("input")
    decode_images.add_argument("output")
    decode_images.add_argument("--output-dir", required=True, help="Directory for decoded image files.")
    decode_images.add_argument("--image-key-config", help="Private config path for image decrypt keys.")
    decode_images.add_argument("--image-aes-key", help="Image AES key. Prefer env/config so shell history stays clean.")
    decode_images.add_argument("--image-xor-key", help="Image XOR key as decimal or hex byte.")
    decode_images.set_defaults(func=_cmd_decode_images)

    image_keys = sub.add_parser("image-keys", help="Diagnose local WeChat image .dat decrypt keys.")
    image_keys_sub = image_keys.add_subparsers(dest="image_keys_command", required=True)
    doctor = image_keys_sub.add_parser("doctor", help="Test keys against .dat files without printing secrets.")
    doctor.add_argument("--dat", action="append", default=[], help="A .dat file or directory. Can be repeated.")
    doctor.add_argument("--conversation", help="Resolved conversation JSON to scan for image .dat attachments.")
    doctor.add_argument("--output-dir", help="Optional directory for decoded test images.")
    doctor.add_argument("--image-key-config", help="Private config path for image decrypt keys.")
    doctor.add_argument("--image-aes-key", help="Image AES key. Prefer env/config so shell history stays clean.")
    doctor.add_argument("--image-xor-key", help="Image XOR key as decimal or hex byte.")
    doctor.add_argument("--save", action="store_true", help="Save provided working keys to private config.")
    doctor.add_argument("--json", action="store_true", help="Print sanitized JSON.")
    doctor.set_defaults(func=_cmd_image_keys_doctor)

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
    pipeline.add_argument("--decode-images", action="store_true", help="Decode image .dat files after media resolution.")
    pipeline.add_argument("--image-key-config", help="Private config path for image decrypt keys.")
    pipeline.add_argument("--image-aes-key", help="Image AES key. Prefer env/config so shell history stays clean.")
    pipeline.add_argument("--image-xor-key", help="Image XOR key as decimal or hex byte.")
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
