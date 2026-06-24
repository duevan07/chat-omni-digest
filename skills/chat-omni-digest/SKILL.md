---
name: chat-omni-digest
description: Use when summarizing exported chat archives with local multimodal enrichment: WeChat text exports, hardlink media/file resolution, image/video/file attachments, Kimi video summaries, Yuanbao public-account article reading, and Markdown/PDF reports.
---

# Chat Omni Digest Skill

Use the local `chatdig` CLI from this repository.

## Workflow

1. Normalize exported chat JSON:

```bash
chatdig normalize input.json work/conversation.json
```

2. Resolve local media and file attachments:

```bash
chatdig resolve-media work/conversation.json work/conversation.resolved.json \
  --account-dir /path/to/wechat/account \
  --hardlink-db /path/to/hardlink.db
```

3. Extract local file text:

```bash
chatdig enrich work/conversation.resolved.json work/conversation.enriched.json
```

4. Generate report:

```bash
chatdig summarize work/conversation.enriched.json outputs/report.md
```

## Privacy

Do not upload private chats, private media, Kimi credentials, Yuanbao browser profiles, decrypted databases, or key extraction logs. Kimi and Yuanbao adapters are optional and must be invoked only when the user explicitly wants external processing.

