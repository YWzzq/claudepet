#!/usr/bin/env python3
"""AgentPet hook 转发入口（Claude Code / Codex 通用）。

从 stdin 读 hook JSON，原样转发给本机 bridge，设计目标是绝不拖慢 CLI：
  - 0.5s 超时，fire-and-forget
  - bridge 不在线 / 任何异常 → 照常退出 0（事件落盘备查）
  - 永远不输出到 stdout，避免污染 CLI

用法（hooks 配置里）：
  python3 /path/to/agentpet_hook.py claude
  python3 /path/to/agentpet_hook.py codex

环境变量：AGENTPET_BRIDGE 默认 http://127.0.0.1:8787/hook
"""

import json
import os
import sys
import time
import urllib.request

SOURCE = sys.argv[1] if len(sys.argv) > 1 else "claude"
BRIDGE = os.environ.get("AGENTPET_BRIDGE", "http://127.0.0.1:18787/hook")
MISSED = os.path.join(os.path.expanduser("~/.agentpet"), "missed-hooks.jsonl")


def save_missed(event):
    try:
        os.makedirs(os.path.dirname(MISSED), exist_ok=True)
        with open(MISSED, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.time(), "source": SOURCE, "event": event},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass


def main():
    # 两种事件入口：Codex notify 把 JSON 作为最后一个命令行参数；
    # Claude Code hooks 走 stdin
    if len(sys.argv) > 2:
        raw = sys.argv[2]
    else:
        raw = sys.stdin.read(65536)
    try:
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        event = {}
    if not isinstance(event, dict):
        return
    event.setdefault("source", SOURCE)

    # Codex 事件采样：记录原始事件类型，用于发现新版本可用的事件
    if SOURCE == "codex":
        try:
            os.makedirs(os.path.dirname(MISSED), exist_ok=True)
            with open(os.path.join(os.path.dirname(MISSED), "codex-events.jsonl"),
                      "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass
    try:
        req = urllib.request.Request(
            BRIDGE, data=json.dumps(event, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=0.5).read(64)
    except Exception:
        save_missed(event)  # bridge 不在线，落盘后照常成功退出


try:
    main()
except Exception:
    pass
sys.exit(0)
