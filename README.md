# Chat Omni Digest

超级融合怪微信聊天记录总结器：一个本地优先的多模态聊天记录解析与摘要管线。

> Public-safe scope: this repository works with already-exported chat JSON or already-decrypted local databases/files. It does not include WeChat key extraction, account login automation, private Kimi credentials, or Yuanbao login state.

## What It Does

- Normalizes exported chat JSON into a stable schema.
- Resolves WeChat images, videos, and file attachments through `hardlink.db`.
- Restores local file paths for PDFs, Office files, images, and videos.
- Decodes classic WeChat image `.dat` files by XOR inference.
- Provides a newer `.dat` v4 decoder hook when `pycryptodome` is installed.
- Extracts local text from PDF, Word, Excel, Markdown, text, CSV, and JSON attachments.
- Generates Markdown and optional PDF digest reports.
- Keeps Kimi video summarization and Yuanbao article reading as optional adapters.

## Reference Projects

This project intentionally studies and consolidates ideas from:

- [huohuoer/wechat-cli](https://github.com/huohuoer/wechat-cli)
- [Wxw-Gu/WechatExplorer](https://github.com/Wxw-Gu/WechatExplorer)
- [Thearas/wechat-db-decrypt-macos](https://github.com/Thearas/wechat-db-decrypt-macos)
- [WeChatMsg_Lite hardlink.py](https://github.com/yann1215/WeChatMsg_Lite/blob/89df85fa9c8107d6147e6a4e9799937bece359dd/wxManager/db_v4/hardlink.py)
- [Chat-Capsule mediaDatResolver.ts](https://github.com/magic8ytes/Chat-Capsule/blob/9e5a18466ede5bfaa6fc271b095a564164d653dc/electron/utils/mediaDatResolver.ts)
- [wx-dump-4j HardLinkImageAttributeMapper.xml](https://github.com/xuchengsheng/wx-dump-4j/blob/b44cba21f79426054af29b98ac795dadfb5e4c4f/wx-dump-admin/src/main/resources/mapper/HardLinkImageAttributeMapper.xml)
- [WcbackMac media_extractor.py](https://github.com/zhaosj0315/WcbackMac/blob/9fa48e30618836f80b6d3b4b28431d2ceed2d053/app/util/media_extractor.py)
- [WeChatDataAnalysis debug_media_lookup.py](https://github.com/LifeArchiveProject/WeChatDataAnalysis/blob/2c9044de01a1ca859f0515db1a39380c6a4ca12e/tools/debug_media_lookup.py)

## Install

```bash
python3 -m pip install -e .
```

Optional extras:

```bash
python3 -m pip install -e ".[pdf,office,media]"
```

## Quick Start

Normalize an exported chat JSON:

```bash
chatdig normalize examples/sample_wechat_digest.json outputs/conversation.json
```

Resolve media and file attachments:

```bash
chatdig resolve-media outputs/conversation.json outputs/conversation.resolved.json \
  --account-dir /path/to/wechat/account \
  --hardlink-db /path/to/hardlink.db \
  --copy-media outputs/media
```

Extract local file text:

```bash
chatdig enrich outputs/conversation.resolved.json outputs/conversation.enriched.json
```

Generate a Markdown report:

```bash
chatdig summarize outputs/conversation.enriched.json outputs/report.md
```

Generate Markdown and PDF together:

```bash
chatdig summarize outputs/conversation.enriched.json outputs/report.md --pdf outputs/report.pdf
```

Or run the local pipeline:

```bash
chatdig pipeline examples/sample_wechat_digest.json \
  --account-dir /path/to/wechat/account \
  --hardlink-db /path/to/hardlink.db \
  --output-dir outputs/demo \
  --pdf \
  --copy-media
```

## Media Resolution Strategy

For images, videos, and files, the resolver tries:

1. Extract `md5`, `filemd5`, file title, URL, and extension from XML-ish message content.
2. Query newer `image_hardlink_info_v3`, `video_hardlink_info_v3`, or `file_hardlink_info_v3`.
3. Query older `HardLinkImageAttribute`, `HardLinkVideoAttribute`, or `HardLinkFileAttribute`.
4. Join or map directory IDs through `dir2id` / `HardLink*ID`.
5. Build candidate paths such as:

```text
msg/attach/<dir1>/<dir2>/Img/<file>
msg/file/<dir1>/<file>
msg/video/<dir1>/<file>
FileStorage/MsgAttach/<dir1>/Image/<dir2>/<file>
FileStorage/File/<dir2>/<file>
```

## Attachment Parsing

After local files are resolved:

- PDF: `pypdf`
- Word: `python-docx`
- Excel: `openpyxl`
- Text/Markdown/CSV/JSON: direct local read
- Video: optional Kimi CLI adapter
- WeChat public-account articles: optional Yuanbao browser bridge adapter

## Optional Kimi Video Adapter

The repository includes an adapter stub for local Kimi CLI:

```text
~/.kimi-code/bin/kimi
```

It is not called by default. Use it only for videos you are comfortable sending to Kimi.

## Optional Yuanbao Article Adapter

The public repository only defines the adapter boundary. Keep any headless browser login state or Yuanbao bridge private.

Recommended contract:

```json
{
  "title": "Article title",
  "summary": "Short article summary",
  "key_points": "Bullet style key points"
}
```

## Privacy And Safety

- Keep decrypted databases, private chat logs, media files, and credentials out of the repository.
- Only run external services such as Kimi or Yuanbao on content you are allowed to upload or process.
- Use this for personal archives, research, and backups you are authorized to access.

## Development

```bash
python3 -m pip install -e ".[dev,pdf,office,media]"
pytest
python3 -m compileall src
```
