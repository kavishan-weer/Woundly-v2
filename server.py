from __future__ import annotations

import base64
import json
import mimetypes
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from model_lib import WoundAnalyzer

ROOT = Path(__file__).resolve().parent
analyzer = None


def get_analyzer():
    global analyzer
    if analyzer is None:
        analyzer = WoundAnalyzer()
    return analyzer


class WoundlyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == "/api/health":
            return self.send_json({"status": "ok"})
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/analyze":
            return self.send_error(HTTPStatus.NOT_FOUND)
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length))
            image_data_url = payload["image"]
            encoded = image_data_url.split(",", 1)[1] if "," in image_data_url else image_data_url
            result = get_analyzer().analyze(base64.b64decode(encoded))
            self.send_json(result)
        except FileNotFoundError as error:
            self.send_json({"error": str(error)}, status=HTTPStatus.SERVICE_UNAVAILABLE)
        except Exception as error:
            self.send_json({"error": f"Analysis failed: {error}"}, status=HTTPStatus.BAD_REQUEST)

    def send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("Woundly running at http://localhost:4173")
    ThreadingHTTPServer(("127.0.0.1", 4173), WoundlyHandler).serve_forever()
