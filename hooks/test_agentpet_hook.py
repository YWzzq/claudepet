"""Exercise the actual forwarding process with native Claude hook payloads."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer


class TestForwarding(unittest.TestCase):
    def setUp(self):
        self.events = queue.Queue()
        events = self.events

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                events.put(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def log_message(self, *args):
                pass

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def forward(self, event, proxy=False):
        env = dict(os.environ, AGENTPET_BRIDGE=
                   f'http://127.0.0.1:{self.server.server_port}/hook')
        if proxy:
            # An unavailable proxy reproduces GUI/CLI proxy inheritance.
            env.update(http_proxy='http://127.0.0.1:1', HTTP_PROXY='http://127.0.0.1:1',
                       no_proxy='', NO_PROXY='')
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name('agentpet_hook.py')), 'claude'],
            input=json.dumps(event), text=True, capture_output=True, env=env, timeout=3)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        return self.events.get(timeout=1)

    def test_session_start_source_is_agent(self):
        for native_source in ('startup', 'resume', 'clear', 'compact'):
            out = self.forward({'hook_event_name': 'SessionStart', 'source': native_source,
                                'session_id': 'fixture'})
            self.assertEqual(out['source'], 'claude')
            self.assertEqual(out['hook_source'], native_source)

    def test_loopback_delivery_bypasses_inherited_proxy(self):
        event = {'hook_event_name': 'PreToolUse', 'tool_name': 'Read', 'session_id': 'fixture'}
        out = self.forward(event, proxy=True)
        self.assertEqual(out, dict(event, source='claude'))


if __name__ == '__main__':
    unittest.main()
