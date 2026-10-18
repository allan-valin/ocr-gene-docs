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


if "--chatty" in sys.argv:
    # a server that talks a lot before it answers: paddle's warnings and
    # kraken's INFO lines fill a pipe nobody reads in a few pages
    for i in range(4000):
        print(f"line {i} " + "x" * 60, flush=True)
if "--die-after" in sys.argv:
    import threading
    delay = float(sys.argv[sys.argv.index("--die-after") + 1])
    threading.Timer(delay, lambda: sys.exit(7)).start()
    import os
    threading.Timer(delay + 0.5, lambda: os._exit(7)).start()
if "--say-device" in sys.argv:
    import os
    print("device=" + os.environ.get("DESEMBARQUE_DEVICE", "unset"), flush=True)
HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
