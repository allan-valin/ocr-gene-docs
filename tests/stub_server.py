"""A stand-in for scripts/serve.py: answers the two calls the launcher makes."""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

STATE = {"status": "idle"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body):
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/api/engine"):
            return self._send({"available": True})
        if self.path.startswith("/api/index"):
            return self._send(STATE)
        return self._send({})

    def do_POST(self):
        if self.path.startswith("/api/index"):
            STATE.update({"status": "running", "done": 0, "skipped": 0,
                          "total": 1, "failed": 0, "eta_s": None})
            return self._send(STATE)
        return self._send({})


HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
