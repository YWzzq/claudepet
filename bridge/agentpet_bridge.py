#!/usr/bin/env python3
"""AgentPet V1.0 — PC 端 Bridge。

职责：接收 hooks 原始事件 → 按规则归一化成状态 → 多 session 优先级仲裁 → 推送到 ESP32。
事件→状态的映射、优先级、超时全部来自 mapping.json（改文件即热加载，不用重启）。
设计约束：hook 端 fire-and-forget；任何坏事件都不能让 /hook 报错或阻塞。

用法：
  python3 agentpet_bridge.py --demo             # 播放脚本事件，演示归一化+仲裁（约 16s）
  python3 agentpet_bridge.py --dry-run          # 不连设备，打印每次状态变化
  python3 agentpet_bridge.py                    # 正常运行，推送 http://agentpet.local
  python3 agentpet_bridge.py --host 192.168.1.23
  python3 agentpet_bridge.py --mapping my.json  # 自定义规则文件（默认 mapping.json）

hooks 调用（V0.6 接入）：
  curl -X POST http://127.0.0.1:18787/hook -d '{"hook_event_name":"PreToolUse",...}'

自测：
  python3 test_bridge.py
"""

import argparse
import fnmatch
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ── 常量 ──
DEFAULT_PORT = 18787     # 8787 常被本机其它服务（如 cloudflared）占用，避开
POLL_S = 1.0             # 仲裁轮询间隔（done 过期的感知精度）

DEFAULT_PRIORITY = {"idle": 0, "thinking": 1, "reading": 2, "shell": 3, "writing": 4,
                    "done": 5, "error": 6, "waiting": 7}
DEFAULT_CFG = {
    "priority": dict(DEFAULT_PRIORITY),
    "done_hold": 5.0,        # done 停留时长，之后该 session 自动回 idle
    "session_timeout": 90.0, # session 无事件后丢弃（与固件 STATE_TIMEOUT_MS 一致）
    "heartbeat": 20.0,       # 无变化也定期推送，喂饱固件的 90s 兜底
}

TOOL_TO_STATE = {
    "Read": "reading", "Grep": "reading", "Glob": "reading", "LS": "reading",
    "WebFetch": "reading", "WebSearch": "reading", "TodoRead": "reading",
    "Edit": "writing", "Write": "writing", "MultiEdit": "writing", "NotebookEdit": "writing",
    "Bash": "shell", "BashOutput": "shell", "KillShell": "shell",
    "Task": "thinking",
}

# mapping.json 缺失/损坏时的兜底规则（与默认 mapping.json 内容一致）
FALLBACK_RULES = [
    {"source": "claude", "event": "SessionStart", "state": "thinking"},
    {"source": "claude", "event": "UserPromptSubmit", "state": "thinking"},
    {"source": "claude", "event": "PreToolUse", "tool": "Read*", "state": "reading"},
    {"source": "claude", "event": "PreToolUse", "tool": "Grep", "state": "reading"},
    {"source": "claude", "event": "PreToolUse", "tool": "Glob", "state": "reading"},
    {"source": "claude", "event": "PreToolUse", "tool": "LS", "state": "reading"},
    {"source": "claude", "event": "PreToolUse", "tool": "WebFetch", "state": "reading"},
    {"source": "claude", "event": "PreToolUse", "tool": "WebSearch", "state": "reading"},
    {"source": "claude", "event": "PreToolUse", "tool": "Edit", "state": "writing"},
    {"source": "claude", "event": "PreToolUse", "tool": "Write", "state": "writing"},
    {"source": "claude", "event": "PreToolUse", "tool": "Bash*", "state": "shell"},
    {"source": "claude", "event": "PreToolUse", "state": "thinking"},
    {"source": "claude", "event": "PostToolUse", "on_error": True, "state": "error"},
    {"source": "claude", "event": "Notification", "state": "waiting", "label_from": "message"},
    {"source": "claude", "event": "Stop", "state": "done"},
    {"source": "claude", "event": "SessionEnd", "state": "__drop__"},
    {"source": "codex", "type": "task_started", "state": "thinking"},
    {"source": "codex", "type": "agent-turn-complete", "state": "done", "label": "turn"},
    {"source": "codex", "type": "error", "state": "error"},
]


def _mk(state, label, source, sid):
    return {"state": state, "label": str(label or "")[:24], "source": source, "session_id": sid}


def load_mapping(path):
    """读取规则文件，返回 (rules, cfg)。文件缺失/损坏时回落内置默认。"""
    rules, cfg = list(FALLBACK_RULES), {**DEFAULT_CFG}
    try:
        with open(path, encoding="utf-8") as f:
            m = json.load(f)
        if isinstance(m.get("rules"), list) and m["rules"]:
            rules = m["rules"]
        if isinstance(m.get("priority"), dict):
            cfg["priority"] = {**DEFAULT_CFG["priority"], **m["priority"]}
        to = m.get("timeouts") or {}
        for k in ("done_hold", "session_timeout", "heartbeat"):
            if k in to:
                cfg[k] = float(to[k])
    except (OSError, ValueError) as e:
        print("[bridge] 规则文件加载失败，使用内置默认: %s" % e)
    return rules, cfg


# 模块级默认规则/配置：从脚本同目录的 mapping.json 加载（缺失则用内置兜底）
_here = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RULES, DEFAULT_CFG = load_mapping(os.path.join(_here, "mapping.json"))


def _is_error_event(raw):
    if raw.get("error"):
        return True
    resp = raw.get("tool_response")
    return isinstance(resp, dict) and bool(resp.get("isError"))


def _canon(event):
    if not isinstance(event, dict):
        return None
    return {
        "source": event.get("source") or "claude",
        "name": event.get("hook_event_name") or event.get("type") or "",
        "tool": str(event.get("tool_name") or event.get("tool") or ""),
        "sid": str(event.get("session_id") or "default"),
        "raw": event,
    }


def _match(rule, ev):
    if "source" in rule and rule["source"] != ev["source"]:
        return False
    for key in ("event", "type"):
        if key in rule and rule[key] != ev["name"]:
            return False
    if "tool" in rule and not fnmatch.fnmatchcase(ev["tool"], rule["tool"]):
        return False
    if rule.get("on_error") and not _is_error_event(ev["raw"]):
        return False
    when = rule.get("when")
    if isinstance(when, dict):
        for k, v in when.items():
            if ev["raw"].get(k) != v:
                return False
    return True


def normalize(event, rules=None):
    """规则驱动的归一化：事件 → 状态字典。

    返回 None 表示忽略该事件；state 为 "__drop__" 表示移除该 session。
    rules 为 None 时使用默认规则（mapping.json 或内置兜底）。
    """
    ev = _canon(event)
    if ev is None:
        return None
    for rule in (rules if rules is not None else DEFAULT_RULES):
        if not isinstance(rule, dict) or not _match(rule, ev):
            continue
        state = rule.get("state")
        if state == "__drop__":
            return _mk("__drop__", "", ev["source"], ev["sid"])
        label = rule.get("label")
        if label is None and "label_from" in rule:
            label = str(ev["raw"].get(rule["label_from"]) or "")
        elif label is None:
            label = ev["tool"]
        return _mk(state, label, ev["source"], ev["sid"])
    return None


class SessionTable:
    """多 session 状态表 + 优先级仲裁（优先级/超时来自 cfg，可热更新）。"""

    def __init__(self, now=time.monotonic, cfg=None):
        self._cfg = {k: dict(v) if isinstance(v, dict) else v for k, v in DEFAULT_CFG.items()}
        if cfg:
            self.update_config(cfg)
        self._sessions = {}
        self._lock = threading.Lock()
        self._now = now

    def update_config(self, cfg):
        if "priority" in cfg and isinstance(cfg["priority"], dict):
            self._cfg["priority"].update(cfg["priority"])
        for k in ("done_hold", "session_timeout"):
            if k in cfg:
                try:
                    self._cfg[k] = float(cfg[k])
                except (TypeError, ValueError):
                    pass

    def apply(self, norm):
        with self._lock:
            if norm["state"] == "__drop__":
                self._sessions.pop(norm["session_id"], None)
            else:
                self._sessions[norm["session_id"]] = {
                    "state": norm["state"],
                    "label": norm["label"],
                    "source": norm["source"],
                    "ts": self._now(),
                }

    def current(self):
        """仲裁：优先级最高者胜，同优先级新的赢。返回 (entry, 活跃 session 数)。"""
        with self._lock:
            now = self._now()
            priority = self._cfg["priority"]
            alive = {}
            for sid, s in self._sessions.items():
                age = now - s["ts"]
                if age > self._cfg["session_timeout"]:
                    continue
                state = s["state"]
                if state == "done" and age > self._cfg["done_hold"]:
                    state = "idle"
                alive[sid] = dict(s, state=state)
            self._sessions = alive
            if not alive:
                return {"state": "idle", "label": "", "source": "", "session_id": ""}, 0
            sid, entry = max(alive.items(),
                             key=lambda kv: (priority.get(kv[1]["state"], 0), kv[1]["ts"]))
            return dict(entry, session_id=sid), len(alive)


def resolve_device(cli_host):
    """设备地址：--host > 环境变量 AGENTPET_HOST > mDNS 名 agentpet.local。"""
    if cli_host:
        return cli_host
    if os.environ.get("AGENTPET_HOST"):
        return os.environ["AGENTPET_HOST"]
    try:
        socket.getaddrinfo("agentpet.local", 80, proto=socket.IPPROTO_TCP)
        return "agentpet.local"
    except OSError:
        return None


class Bridge:
    def __init__(self, device_host=None, dry_run=False, mapping_path=None):
        self.table = SessionTable()
        self.device_host = device_host
        self.dry_run = dry_run
        self.started = time.monotonic()
        self._lock = threading.Lock()
        self._last_key = None
        self._last_push_ts = 0.0
        self.push_ok = 0
        self.push_fail = 0
        self._wake = threading.Event()  # 事件驱动：状态来了立即推，不等轮询
        self.mapping_path = mapping_path
        self.rules = DEFAULT_RULES
        self._map_mtime = None
        if mapping_path:
            self.reload_mapping(log=False)

    def reload_mapping(self, log=True):
        rules, mcfg = load_mapping(self.mapping_path)
        self.rules = rules
        self.table.update_config(mcfg)
        try:
            self._map_mtime = os.path.getmtime(self.mapping_path)
        except OSError:
            self._map_mtime = None
        if log:
            print("[bridge] mapping 已热加载（%d 条规则）" % len(rules))

    def on_event(self, event):
        norm = normalize(event, self.rules)
        if norm is not None:
            self.table.apply(norm)
            self._wake.set()

    def poll(self):
        """仲裁一次并按需推送。返回 (payload, pushed)。"""
        entry, n = self.table.current()
        payload = {"source": entry["source"], "state": entry["state"],
                   "label": entry["label"], "session_id": entry["session_id"]}
        key = json.dumps(payload, sort_keys=True)
        now = time.monotonic()
        with self._lock:
            changed = key != self._last_key
            heartbeat = (now - self._last_push_ts) >= self.table._cfg.get("heartbeat", 20.0)
            if not changed and not heartbeat:
                return payload, False
            self._last_key = key
            self._last_push_ts = now
        if self.dry_run:
            self.push_ok += 1
        else:
            self._push(payload)
        return payload, True

    def _push(self, payload):
        if not self.device_host:
            print("[bridge] 设备地址未知（--host 或 mDNS），本次不推送")
            return
        try:
            req = urllib.request.Request(
                "http://%s/api/v1/state" % self.device_host,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST")
            urllib.request.urlopen(req, timeout=2)
            self.push_ok += 1
        except OSError as e:
            self.push_fail += 1
            print("[bridge] 推送失败: %s (%s)" % (self.device_host, e))

    def loop(self):
        print("[bridge] 运行中：hooks → http://127.0.0.1:%d/hook，设备 → %s"
              % (ARGS.port, self.device_host or "未知（每 20s 重试解析）"))
        while True:
            # 事件到达立即醒来推送；1s 超时兜底感知 done 过期等时间性变化
            self._wake.wait(POLL_S)
            self._wake.clear()
            if self.mapping_path:
                self.check_reload()
            payload, pushed = self.poll()
            if pushed:
                print("[push] %s" % json.dumps(payload, ensure_ascii=False))

    def check_reload(self):
        try:
            mtime = os.path.getmtime(self.mapping_path)
        except OSError:
            return
        if self._map_mtime is None or mtime != self._map_mtime:
            self.reload_mapping()


def make_server(bridge, port):
    """hooks 的本地 HTTP 入口。对 hooks 永远友好：坏请求也返回 204，绝不抛错。"""
    here = os.path.dirname(os.path.abspath(__file__))

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path == "/hook":
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                try:
                    bridge.on_event(json.loads(raw.decode("utf-8") or "{}"))
                except (ValueError, UnicodeDecodeError):
                    pass  # 坏事件静默吞掉
            self.send_response(204)
            self.end_headers()

        def do_GET(self):
            if self.path in ("/", "/ui"):
                # 配置台页面：每次现读文件，改完刷新即生效
                try:
                    ui = open(os.path.join(here, "webui.html"), encoding="utf-8").read()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(ui.encode("utf-8"))))
                    self.end_headers()
                    self.wfile.write(ui.encode("utf-8"))
                except OSError:
                    self.send_response(404); self.end_headers()
            elif self.path == "/api/v1/mapping":
                try:
                    body = open(bridge.mapping_path, "rb").read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    self.send_response(404); self.end_headers()
            elif self.path == "/health":
                entry, n = bridge.table.current()
                body = json.dumps({
                    "uptime_s": round(time.monotonic() - bridge.started, 1),
                    "state": entry["state"],
                    "label": entry["label"],
                    "sessions": n,
                    "device": bridge.device_host,
                    "push_ok": bridge.push_ok,
                    "push_fail": bridge.push_fail,
                }, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def do_PUT(self):
            if self.path == "/api/v1/mapping":
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                try:
                    json.loads(raw.decode("utf-8"))
                except Exception:
                    self.send_response(400); self.end_headers(); return
                try:
                    with open(bridge.mapping_path, "wb") as f:
                        f.write(raw)
                    bridge.reload_mapping(log=True)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true,"reloaded":true}')
                except OSError:
                    self.send_response(500); self.end_headers()
            else:
                self.send_response(404); self.end_headers()

        def log_message(self, *args):
            pass  # 静默访问日志，hooks 高频调用不刷屏

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


# ── 演示脚本：双会话 + 优先级抢占 + done 过期 ──
# 时间线要卡在 DONE_HOLD_S 之外：s2 在 8.0s 进入 done，13s 才过期
DEMO_SCRIPT = [
    (0.0, {"hook_event_name": "UserPromptSubmit", "source": "claude", "session_id": "s1"}),
    (1.5, {"hook_event_name": "PreToolUse", "tool_name": "Read", "session_id": "s1"}),
    (3.0, {"hook_event_name": "PreToolUse", "tool_name": "Edit", "session_id": "s1"}),
    (4.5, {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "s2"}),
    (6.0, {"hook_event_name": "Notification", "message": "需要授权", "session_id": "s2"}),
    (8.0, {"hook_event_name": "Stop", "session_id": "s2"}),
    (13.5, None),  # 等 s2 的 done 过期，s1 的 writing 重新浮上来
    (15.0, {"hook_event_name": "SessionEnd", "session_id": "s1"}),
]


def run_demo(bridge):
    print("=== AgentPet Bridge 演示：双会话 + 优先级仲裁 + done 过期 ===")
    t0 = time.monotonic()
    for at, ev in DEMO_SCRIPT:
        delay = at - (time.monotonic() - t0)
        if delay > 0:
            time.sleep(delay)
        if ev is None:
            print("[%5.1fs] --- 等 done 过期，看谁浮上来 ---" % at)
        else:
            print("[%5.1fs] hook  %s" % (at, json.dumps(ev, ensure_ascii=False)))
            bridge.on_event(ev)
        payload, pushed = bridge.poll()
        mark = "推送到设备" if pushed else "显示不变"
        print("        → 屏幕: %s %s (%s)  [%s]"
              % (payload["state"], payload["label"], payload["source"] or "-", mark))
    print("=== 演示结束 ===")


ARGS = None


def main():
    global ARGS
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description="AgentPet V1.0 Bridge")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="hooks 本地入口端口")
    parser.add_argument("--host", default=None, help="ESP32 地址，默认解析 agentpet.local")
    parser.add_argument("--dry-run", action="store_true", help="不连设备，只打印推送")
    parser.add_argument("--demo", action="store_true", help="播放脚本事件演示仲裁")
    parser.add_argument("--mapping", default=os.path.join(here, "mapping.json"),
                        help="规则文件路径（默认 mapping.json，支持热加载）")
    ARGS = parser.parse_args()

    device = None if (ARGS.dry_run or ARGS.demo) else resolve_device(ARGS.host)
    bridge = Bridge(device_host=device, dry_run=True if ARGS.demo else ARGS.dry_run,
                    mapping_path=ARGS.mapping)

    if ARGS.demo:
        run_demo(bridge)
        return

    t = threading.Thread(target=bridge.loop, daemon=True)
    t.start()
    try:
        make_server(bridge, ARGS.port).serve_forever()
    except OSError as e:
        print("[bridge] 端口 %d 启动失败: %s" % (ARGS.port, e))
        print("        换一个端口试试：python3 agentpet_bridge.py --port 28787")
        print("        （hooks 侧同步改环境变量 AGENTPET_BRIDGE=http://127.0.0.1:28787/hook）")
        sys.exit(1)


if __name__ == "__main__":
    main()
