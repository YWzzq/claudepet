#!/bin/bash
# AgentPet Codex 通知分发器：
# Codex 的 notify 只能配一个程序，此脚本把事件同时送给：
#   1) AgentPet bridge（本机 18787/hook）
#   2) 原有 notify 程序（安装时自动捕获，见下方 ORIGINAL 变量）
# Codex 调用格式：dispatcher <原参数...> '<事件JSON>'

ORIGINAL="/Users/yws/.codex/computer-use/Codex Computer Use.app/Contents/SharedSupport/SkyComputerUseClient.app/Contents/MacOS/SkyComputerUseClient"

LAST_ARG="${@: -1}"
python3 /Users/yws/data/2026/claudecode/agentpet/hooks/agentpet_hook.py codex "$LAST_ARG" >/dev/null 2>&1 &

exec "$ORIGINAL" "$@"
