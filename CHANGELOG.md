# Changelog

## 0.1.2 - 2026-06-25

- Added `chatdig image-keys doctor` to test WeChat image `.dat` key readiness without printing secrets.
- Added `chatdig decode-images` and `pipeline --decode-images` for decoding resolved image `.dat` attachments when local image AES/XOR keys are available.
- Added V2 `.dat` decoding through the public CLI and tests for AES/XOR image decoding.

## 0.1.1 - 2026-06-25

- Added a Mac WeChat `message_resource.db` bridge for image messages that only export as `[图片]`.
- Added `--message-resource-db` to `resolve-media` and `pipeline`.
- Added report cleanup for binary app-message payloads that are not decoded yet.

## 0.1.0 - 2026-06-24

First packaged release.

- Added the `chatdig` command-line interface.
- Added chat JSON normalization into a stable local schema.
- Added WeChat hardlink media resolution for images, videos, and file attachments.
- Added classic `.dat` XOR decoding and a V4 AES/XOR decoder hook.
- Added local attachment text extraction for PDF, Word, Excel, Markdown, text, CSV, and JSON files.
- Added Markdown and optional PDF report generation.
- Added optional adapter boundaries for Kimi video summaries and Yuanbao public-account article reading.
- Added a reusable Codex skill in `skills/chat-omni-digest`.
