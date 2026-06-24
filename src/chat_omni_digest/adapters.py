from __future__ import annotations

import json
import subprocess
from pathlib import Path


class ExternalToolError(RuntimeError):
    pass


def summarize_video_with_kimi(video_path: str | Path, prompt: str | None = None, timeout: int = 600) -> str:
    """Optional Kimi CLI adapter.

    This intentionally does not run unless called. Different Kimi CLI versions
    expose different flags, so this adapter keeps the command narrow and easy
    to override later.
    """
    kimi = Path.home() / ".kimi-code" / "bin" / "kimi"
    if not kimi.exists():
        raise ExternalToolError("Kimi CLI not found at ~/.kimi-code/bin/kimi")
    request = prompt or "请总结这个视频的主要内容、关键信息和可用于聊天记录摘要的要点。"
    cmd = [str(kimi), request, str(video_path)]
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise ExternalToolError(result.stderr.strip() or "Kimi CLI failed")
    return result.stdout.strip()


def summarize_article_with_yuanbao(url: str, output_json: str | Path | None = None) -> dict[str, str]:
    """Placeholder adapter for a local Yuanbao browser bridge.

    Keep this local/private in real deployments. Public repository users can
    implement the bridge contract by returning a JSON object with title,
    summary, and key_points.
    """
    if output_json:
        data = json.loads(Path(output_json).read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()}
    raise ExternalToolError("Yuanbao bridge is not configured")

