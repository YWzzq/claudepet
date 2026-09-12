"""AgentPet Bridge 单元测试（不依赖硬件，python3 test_bridge.py 直接跑）。"""

import unittest

from agentpet_bridge import DEFAULT_PRIORITY, SessionTable, normalize


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def now(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def norm_of(event):
    out = normalize(event)
    assert out is not None, "事件被忽略: %r" % event
    return out


class TestNormalize(unittest.TestCase):
    def test_claude_prompt_and_session_start(self):
        for name in ("UserPromptSubmit", "SessionStart"):
            out = norm_of({"hook_event_name": name, "session_id": "a"})
            self.assertEqual(out["state"], "thinking")

    def test_tool_mapping(self):
        cases = {
            "Read": "reading", "Grep": "reading", "WebFetch": "reading",
            "Edit": "writing", "Write": "writing",
            "Bash": "shell", "BashOutput": "shell",
            "UnknownTool": "thinking",
        }
        for tool, state in cases.items():
            out = norm_of({"hook_event_name": "PreToolUse", "tool_name": tool})
            self.assertEqual(out["state"], state, tool)

    def test_tool_glob_rule(self):
        # 规则里的通配符：Bash* 应命中 Bash/BashOutput/KillBash 等
        for tool in ("Bash", "BashOutput", "BashRandom"):
            out = norm_of({"hook_event_name": "PreToolUse", "tool_name": tool})
            self.assertEqual(out["state"], "shell", tool)
        # Edit* 不该误伤 Edito
        out = norm_of({"hook_event_name": "PreToolUse", "tool_name": "Edito"})
        self.assertEqual(out["state"], "thinking")

    def test_custom_rules(self):
        rules = [{"event": "CoffeeBreak", "state": "tea"}]
        out = normalize({"hook_event_name": "CoffeeBreak"}, rules)
        self.assertEqual(out["state"], "tea")
        # 不匹配规则的其余事件照常回落
        self.assertIsNone(normalize({"hook_event_name": "Other"}, rules))

    def test_rule_label_from_field(self):
        rules = [{"event": "Say", "state": "waiting", "label_from": "text"}]
        out = normalize({"hook_event_name": "Say", "text": "你好"}, rules)
        self.assertEqual(out["state"], "waiting")
        self.assertEqual(out["label"], "你好")
        # 未指定 label/label_from 时回落工具名
        rules2 = [{"event": "Say", "state": "waiting", "tool": "Pen"}]
        out2 = normalize({"hook_event_name": "Say", "tool": "Pen"}, rules2)
        self.assertEqual(out2["label"], "Pen")

    def test_notification_is_waiting(self):
        out = norm_of({"hook_event_name": "Notification", "message": "需要授权"})
        self.assertEqual(out["state"], "waiting")
        self.assertEqual(out["label"], "需要授权")

    def test_stop_is_done(self):
        self.assertEqual(norm_of({"hook_event_name": "Stop"})["state"], "done")

    def test_session_end_is_drop(self):
        self.assertEqual(norm_of({"hook_event_name": "SessionEnd"})["state"], "__drop__")

    def test_post_tool_use_normal_ignored(self):
        self.assertIsNone(normalize(
            {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_response": {"ok": True}}))

    def test_post_tool_use_error(self):
        out = norm_of({"hook_event_name": "PostToolUse", "tool_name": "Bash",
                       "tool_response": {"isError": True}})
        self.assertEqual(out["state"], "error")

    def test_codex_events(self):
        self.assertEqual(
            normalize({"source": "codex", "type": "task_started"})["state"], "thinking")
        self.assertEqual(
            normalize({"source": "codex", "type": "agent-turn-complete"})["state"], "done")

    def test_bad_events(self):
        self.assertIsNone(normalize(None))
        self.assertIsNone(normalize("not a dict"))
        self.assertIsNone(normalize({"hook_event_name": "Whatever"}))


class TestArbitration(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.table = SessionTable(now=self.clock.now)

    def feed(self, sid, state, label=""):
        self.table.apply({"state": state, "label": label, "source": "claude",
                          "session_id": sid})

    def current_state(self):
        entry, n = self.table.current()
        return entry["state"], n

    def test_waiting_beats_everything(self):
        self.feed("s1", "writing")
        self.feed("s2", "shell")
        self.feed("s3", "waiting")
        state, n = self.current_state()
        self.assertEqual((state, n), ("waiting", 3))

    def test_writing_beats_shell(self):
        self.feed("s1", "writing")
        self.feed("s2", "shell")
        self.assertEqual(self.current_state()[0], "writing")

    def test_same_priority_newest_wins(self):
        self.feed("s1", "reading", label="old")
        self.clock.advance(1)
        self.feed("s2", "reading", label="new")
        entry, _ = self.table.current()
        self.assertEqual(entry["session_id"], "s2")

    def test_done_expires_then_lower_priority_returns(self):
        self.feed("s1", "writing")
        self.clock.advance(1)
        self.feed("s2", "done")
        self.assertEqual(self.current_state()[0], "done")   # done(5) > writing(4)
        self.clock.advance(6)
        self.assertEqual(self.current_state()[0], "writing")  # done 过期，writing 浮出

    def test_session_timeout_drops_to_idle(self):
        self.feed("s1", "writing")
        self.clock.advance(91)
        self.assertEqual(self.current_state(), ("idle", 0))

    def test_drop_removes_session(self):
        self.feed("s1", "waiting")
        self.table.apply({"state": "__drop__", "label": "", "source": "claude",
                          "session_id": "s1"})
        self.assertEqual(self.current_state(), ("idle", 0))

    def test_empty_table_is_idle(self):
        self.assertEqual(self.current_state(), ("idle", 0))


if __name__ == "__main__":
    unittest.main()
