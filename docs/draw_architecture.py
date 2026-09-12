# AgentPet V0 架构图生成脚本（python3 draw_architecture.py）
import os
import matplotlib

matplotlib.use("Agg")
from matplotlib import font_manager as fm
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

for p in ["/System/Library/Fonts/Hiragino Sans GB.ttc", "/Library/Fonts/Arial Unicode.ttf"]:
    if os.path.exists(p):
        fm.fontManager.addfont(p)
plt.rcParams["font.sans-serif"] = ["Hiragino Sans GB", "Arial Unicode MS", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

INK, ARROW, GRAY = "#1F2937", "#5B6472", "#6B7280"
MONO = {"family": "Menlo", "size": 9.5}

fig, ax = plt.subplots(figsize=(14, 10), dpi=150)
ax.set_xlim(0, 14); ax.set_ylim(0, 10); ax.axis("off")

def box(x, y, w, h, fc, ec, text="", fs=12, tc=INK, bold=False, lw=1.4, rs=0.10):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle=f"round,pad=0.02,rounding_size={rs}",
                 facecolor=fc, edgecolor=ec, linewidth=lw))
    if text:
        ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs,
                color=tc, fontweight="bold" if bold else "normal", linespacing=1.5)

def arrow(x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=ARROW, lw=1.8,
                                shrinkA=0, shrinkB=0, mutation_scale=16))

def note(x, y, text, fs=10, color=GRAY, ha="left"):
    ax.text(x, y, text, ha=ha, va="center", fontsize=fs, color=color)

# ── 标题 ─────────────────────────────────────────────
ax.text(7, 9.62, "AgentPet V0 系统架构", ha="center", fontsize=22, fontweight="bold", color=INK)
ax.text(7, 9.18, "PC 端 Hooks → Bridge → Wi-Fi HTTP → ESP32-S3 → ST7789 桌宠",
        ha="center", fontsize=11, color=GRAY)

# ── PC 端容器 ────────────────────────────────────────
box(0.5, 4.9, 13.0, 3.9, "#EEF4FB", "#4A78A8", lw=1.6, rs=0.14)
ax.text(0.85, 8.42, "PC 端（你的电脑）", fontsize=13, fontweight="bold", color="#2C5A8A")

box(1.0, 7.25, 3.4, 0.85, "#FFFFFF", "#4A78A8", "Claude Code", 13)
box(5.0, 7.25, 3.4, 0.85, "#FFFFFF", "#4A78A8", "Codex CLI", 13)
note(9.0, 7.68, "同一台电脑可同时跑多个会话、多个 Agent")

box(1.0, 5.95, 7.4, 0.85, "#DCEBFB", "#4A78A8",
    "Hooks（极小脚本 · fire-and-forget · 绝不阻塞 CLI）", 11.5)
box(1.0, 5.00, 7.4, 0.85, "#CFE3F9", "#4A78A8",
    "Python Bridge（归一化 → session 优先级仲裁 → 心跳）", 11.5)
note(4.95, 5.925, "", 8)
ax.text(8.55, 6.38, "本地 HTTP\n127.0.0.1:18787", ha="center", va="center",
        fontsize=9, color=GRAY, linespacing=1.4)

box(8.9, 5.35, 4.2, 0.75, "#1E2430", "#1E2430")
ax.text(11.0, 5.725, '{"tool":"Edit"}  →  writing', ha="center", va="center",
        fontsize=9.5, color="#E5E7EB", family="Menlo")
note(11.0, 6.45, "hook 只发原始事件\n归一化是 bridge 的事", fs=9.5, ha="center")

arrow(2.7, 7.25, 2.7, 6.83)
arrow(6.7, 7.25, 6.7, 6.83)
arrow(4.7, 5.95, 4.7, 5.88)

# ── PC → ESP32 ──────────────────────────────────────
arrow(4.7, 4.9, 4.7, 4.18)
ax.text(5.05, 4.72, "Wi-Fi（局域网 HTTP）· mDNS: agentpet.local", fontsize=11, color=INK)
ax.text(5.05, 4.38, "POST /api/v1/state   {source, state, label, session_id}",
        fontsize=9.5, color=GRAY, family="Menlo")

# ── ESP32-S3 容器 ────────────────────────────────────
box(0.5, 0.55, 13.0, 3.6, "#EDF7F0", "#3F8F63", lw=1.6, rs=0.14)
ax.text(0.85, 3.82, "ESP32-S3（桌面摆件 · USB-C 供电 · N16R8）",
        fontsize=13, fontweight="bold", color="#2E6B47")

box(1.0, 2.55, 2.1, 0.8, "#FFFFFF", "#3F8F63", "Wi-Fi 管理", 12)
box(3.5, 2.55, 2.4, 0.8, "#FFFFFF", "#3F8F63", "HTTP Server", 12)
box(6.3, 2.55, 1.9, 0.8, "#FFFFFF", "#3F8F63", "状态机", 12)
box(8.6, 2.55, 2.2, 0.8, "#FFFFFF", "#3F8F63", "动画引擎", 12)
box(11.2, 2.55, 2.3, 0.8, "#DFF1E6", "#3F8F63", "ST7789 240×240", 12)
arrow(3.1, 2.95, 3.48, 2.95); arrow(5.9, 2.95, 6.28, 2.95)
arrow(8.2, 2.95, 8.58, 2.95); arrow(10.8, 2.95, 11.18, 2.95)

note(1.0, 1.85, "GET /api/v1/health —— 当前状态 / Wi-Fi RSSI / uptime / 堆内存（调试）", fs=10)
note(1.0, 1.42, "兜底：90 秒无更新 → 自动回 idle；done 停留 5 秒 → idle", fs=10)
note(1.0, 0.99, "设备只懂 REST + 表情，不关心跑的是哪个 Agent（Tiny Engineer 思路）", fs=10)
box(9.3, 0.95, 3.9, 0.62, "#DFF1E6", "#3F8F63", "", 10)
ax.text(11.25, 1.26, "agentpet.local · 端口 80", ha="center", va="center",
        fontsize=9.5, color="#2E6B47")

# ── 8 状态图例 ───────────────────────────────────────
states = [("idle", "#98A2B3"), ("thinking", "#A78BFA"), ("reading", "#3B82F6"),
          ("writing", "#22C55E"), ("shell", "#0EA5E9"), ("waiting", "#F59E0B"),
          ("done", "#10B981"), ("error", "#EF4444")]
ax.text(0.55, 0.18, "8 状态", fontsize=10, fontweight="bold", color=INK, va="center")
for i, (name, c) in enumerate(states):
    x = 1.75 + i * 1.55
    ax.add_patch(plt.Circle((x, 0.18), 0.09, color=c))
    ax.text(x + 0.17, 0.18, name, fontsize=10, color=INK, va="center")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "architecture.png")
fig.savefig(out, bbox_inches="tight", facecolor="white")
print("saved:", out)
