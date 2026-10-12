"""Exercise the UI proxy against a local device stub, without hardware."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

from agentpet_bridge import make_server


class DeviceProxyTest(unittest.TestCase):
    def setUp(self):
        self.received = []
        received = self.received

        class Device(BaseHTTPRequestHandler):
            def handle_request(self):
                body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                received.append((self.command, self.path, body))
                data = json.dumps({'ok': self.path != '/api/v1/states/missing'}).encode()
                self.send_response(404 if self.path.endswith('/missing') else 200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_PUT = do_POST = do_DELETE = handle_request

            def log_message(self, *args):
                pass

        self.device = ThreadingHTTPServer(('127.0.0.1', 0), Device)
        self.bridge = make_server(SimpleNamespace(
            device_host='127.0.0.1:' + str(self.device.server_port)), 0)
        for server in (self.device, self.bridge):
            threading.Thread(target=server.serve_forever, daemon=True).start()
        self.base = 'http://127.0.0.1:' + str(self.bridge.server_port)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        for server in (self.bridge, self.device):
            server.shutdown()
            server.server_close()

    def request(self, path, method='GET', body=None, headers=None):
        req = urllib.request.Request(self.base + path, data=body, method=method,
                                     headers=headers or {})
        try:
            response = self.opener.open(req, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read()

    def test_forwarding_and_device_errors(self):
        recipe = b'{"led":{"color":"#123456"},"screen":{"pose":"idle"}}'
        for method, path, body in (
            ('GET', '/api/v1/states', None),
            ('PUT', '/api/v1/states/idle', recipe),
            ('POST', '/api/v1/state', b'{"state":"idle"}'),
            ('DELETE', '/api/v1/states/test', None),
        ):
            status, data = self.request('/board' + path, method, body,
                                        {'Origin': self.base})
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(data)['ok'])
            self.assertEqual(self.received[-1], (method, path, body or b''))
        self.assertEqual(self.request('/board/api/v1/states/missing')[0], 404)

    def test_rejects_unrelated_routes_and_foreign_origins(self):
        self.assertEqual(self.request('/board/private')[0], 404)
        self.assertEqual(self.request('/board/api/v1/states', headers={
            'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.received, [])

    def test_invalid_or_large_body(self):
        for length, status in [('invalid', 400), ('-1', 400), ('65537', 413)]:
            self.assertEqual(self.request('/board/api/v1/state', 'POST',
                                         headers={'Content-Length': length})[0], status)
        self.assertEqual(self.received, [])


if __name__ == '__main__':
    unittest.main()
