#!/usr/bin/env python3
"""AgentPet 虚拟设备 —— 在终端里模拟 ESP32 摆件。

实现与固件相同的 HTTP 接口，收到状态就画一张终端表情脸：
  POST /api/v1/state   {"source":"claude","state":"writing","label":"Edit"}
  GET  /api/v1/health

用法（配合 bridge）：
  python3 tools/virtual_device.py 8080          # 终端 A：跑虚拟设备
  AGENTPET_HOST=127.0.0.1:8080 python3 bridge/agentpet_bridge.py   # 终端 B：bridge 指向它
"""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
STARTED = time.time()

# 与固件/模拟器同一套状态色（真彩 ANSI）
FG = {
    "idle": (140, 155, 171), "thinking": (157, 143, 255), "reading": (90, 162, 240),
    "writing": (79, 207, 132), "shell": (59, 184, 232), "waiting": (255, 176, 58),
    "done": (59, 214, 146), "error": (240, 72, 72),
}
# 每个状态的 (眼睛, 嘴, 额外符号)
FACE = {
    "idle": ("-  -", "", "z"),
    "thinking": ("*  *", "----", "..."),
    "reading": ("o  o", "----", ""),
    "writing": (".  .", "o", ""),
    "shell": ("*  *", "> _", ""),
    "waiting": ("O  O", "?", ""),
    "done": ("^  ^", "‿‿‿", ""),
    "error": ("x  x", "~~~", "!!"),
}
UNKNOWN = {"state": "?", "label": "", "source": "", "since": time.time()}


def color(s):
    r, g, b = FG.get(s, (200, 200, 200))
    return "\033[38;2;%d;%d;%dm" % (r, g, b)


def draw(s):
    st = s["state"]
    eyes, mouth, extra = FACE.get(st, ("?  ?", "?", ""))
    c = color(st)
    dim = "\033[2m"
    W = 30
    def row(inner):
        pad = max(0, (W - 2 - len(inner)) // 2)
        return c + "│" + "\033[0m" + " " * pad + (c + inner + "\033[0m" if inner else "")
    print()
    print(c + "╭" + "─" * W + "╮\033[0m")
    for line in ("", extra, eyes, "", mouth, ""):
        body = row(line) + c + "│\033[0m"
        print(body)
    print(c + "╰" + "─" * W + "╯\033[0m")
    print(dim + "  %s · %s%s  [%s]  %s\033[0m" % (
        s["source"] or "-", st, ' "' + s["label"] + '"' if s["label"] else "",
        time.strftime("%H:%M:%S"), "(%d 个会话)" % s.get("sessions", 1) if s.get("sessions", 1) > 1 else ""))


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/v1/state":
            self.send_response(404); self.end_headers(); return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            body = {}
        if body.get("state"):
            UNKNOWN.update(state=body.get("state"), label=body.get("label", ""),
                           source=body.get("source", ""), since=time.time())
            draw(UNKNOWN)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_GET(self):
        if self.path == "/api/v1/health":
            body = json.dumps({
                "device": "virtual-dev", "state": UNKNOWN["state"],
                "label": UNKNOWN["label"], "source": UNKNOWN["source"],
                "state_for_s": round(time.time() - UNKNOWN["since"]),
                "uptime_s": round(time.time() - STARTED),
                "ip": "127.0.0.1", "wifi": "virtual", "rssi": -42,
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print("[virtual-dev] 监听 :%d —— 这就是你的 ESP32（终端版）" % PORT)
    print("[virtual-dev] 把 bridge 指向这里：AGENTPET_HOST=127.0.0.1:%d" % PORT)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
