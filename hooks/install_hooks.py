#!/usr/bin/env python3
"""AgentPet hooks 一键安装器。

- Claude Code：把 agentpet hook 合并进 ~/.claude/settings.json 的 hooks 块
- Codex：写入/合并 ~/.codex/hooks.json（Codex 的 hooks 支持随版本演进，
  如果你的版本格式不同，请以官方文档为准微调本文件里的 CODEX_CONFIG）

安全措施：
  - 写入前自动备份原文件（.bak-时间戳）
  - 幂等：重复运行不会产生重复 hook 条目
  - 只增不删：不碰你已有的其它 hooks

用法：
  python3 install_hooks.py            # 同时安装 claude + codex
  python3 install_hooks.py --claude   # 只装 Claude Code
  python3 install_hooks.py --codex    # 只装 Codex
"""

import argparse
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK_CMD = "python3 %s/agentpet_hook.py %%s" % HERE

CLAUDE_SETTINGS = os.path.expanduser("~/.claude/settings.json")
CODEX_CONFIG = os.path.expanduser("~/.codex/hooks.json")

# AgentPet 关心的 Claude Code 事件 → 都转发给同一个脚本
CLAUDE_EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                 "Notification", "Stop", "SessionEnd"]


def backup(path):
    if os.path.exists(path):
        dst = "%s.bak-%s" % (path, time.strftime("%Y%m%d%H%M%S"))
        shutil.copy2(path, dst)
        print("  已备份: %s -> %s" % (path, dst))


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def entry_contains_cmd(entries, cmd):
    """递归判断 hook 条目列表里是否已有我们的命令（幂等检查）。"""
    if isinstance(entries, dict):
        return any(entry_contains_cmd(v, cmd) for v in entries.values())
    if isinstance(entries, list):
        return any(entry_contains_cmd(v, cmd) for v in entries)
    return isinstance(entries, str) and cmd in entries


def install_claude():
    print("== Claude Code ==")
    cmd = HOOK_CMD % "claude"
    data = {}
    if os.path.exists(CLAUDE_SETTINGS):
        backup(CLAUDE_SETTINGS)
        data = read_json(CLAUDE_SETTINGS)
    hooks = data.setdefault("hooks", {})
    added = []
    for ev in CLAUDE_EVENTS:
        group = hooks.setdefault(ev, [])
        if entry_contains_cmd(group, cmd):
            continue  # 已装过，跳过
        group.append({"hooks": [{"type": "command", "command": cmd}]})
        added.append(ev)
    write_json(CLAUDE_SETTINGS, data)
    if added:
        print("  已写入 %d 个事件: %s" % (len(added), ", ".join(added)))
    else:
        print("  已存在，无需修改")
    print("  配置: %s" % CLAUDE_SETTINGS)


def install_codex():
    print("== Codex ==")
    cmd = HOOK_CMD % "codex"
    data = {}
    if os.path.exists(CODEX_CONFIG):
        backup(CODEX_CONFIG)
        try:
            data = read_json(CODEX_CONFIG)
        except json.JSONDecodeError:
            print("  警告: 已有 %s 不是合法 JSON，将重命名保留" % CODEX_CONFIG)
            backup(CODEX_CONFIG)
            data = {}
    hook_list = data.get("hooks") if isinstance(data.get("hooks"), list) else []
    if not entry_contains_cmd(hook_list, cmd):
        hook_list.append({
            "match": {"event": ["session_start", "user_prompt", "task_started",
                                "tool_use", "agent_turn_complete", "error"]},
            "action": {"type": "command", "command": cmd},
        })
        data["hooks"] = hook_list
        write_json(CODEX_CONFIG, data)
        print("  已写入 1 条 hook 转发规则")
    else:
        print("  已存在，无需修改")
    print("  配置: %s" % CODEX_CONFIG)
    print("  注意: Codex 的 hooks/notify 配置格式随版本演进，若不生效请对照官方文档微调")


def main():
    parser = argparse.ArgumentParser(description="AgentPet hooks 一键安装器")
    parser.add_argument("--claude", action="store_true")
    parser.add_argument("--codex", action="store_true")
    args = parser.parse_args()
    if not (args.claude or args.codex):
        args.claude = args.codex = True
    if args.claude:
        install_claude()
    if args.codex:
        install_codex()
    print("\n完成。启动 bridge 即可看到状态：python3 bridge/agentpet_bridge.py --dry-run")
    print("卸载：删除配置里包含 agentpet_hook.py 的条目即可（安装时未改动其它内容）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
