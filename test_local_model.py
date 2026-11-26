import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
from local_model import endpoint, propose


class LocalModelTest(unittest.TestCase):
    def test_endpoint_restrictions(self):
        self.assertEqual(endpoint("http://127.0.0.1:1234/v1"),
                         "http://127.0.0.1:1234/v1/chat/completions")
        for url in ("https://example.com/v1", "http://localhost/v1",
                    "http://127.0.0.1@evil.example/v1", "http://127.0.0.1/v1?x=1"):
            with self.assertRaises(ValueError):
                endpoint(url)

    def test_loopback_exchange(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                body = json.dumps({"choices": [{"message": {"content":
                    json.dumps({"packet_id": "test", "action": "deliver_aid"})}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        with HTTPServer(("127.0.0.1", 0), Handler) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                with patch("local_model.packet", return_value={"packet_id": "test"}), \
                     patch("local_model.validate_proposal", return_value={"status": "requires_confirmation"}) as validator:
                    result = propose({}, "deliver aid", "test-model",
                                     "http://127.0.0.1:%s/v1" % server.server_port)
                    validator.assert_called_once()
                self.assertEqual(result["response"]["action"], "deliver_aid")
                self.assertEqual(result["proposal"]["status"], "requires_confirmation")
                self.assertEqual(requests[0][0], "/v1/chat/completions")
                self.assertEqual(requests[0][1]["model"], "test-model")
            finally:
                server.shutdown()
                worker.join()
