"""src/reading/engines/vlm.py testlari — haqiqiy modelsiz, soxta lokal server bilan."""

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import cv2
import numpy as np
import pytest

from src.reading.engines.vlm import MAX_SIDE, VlmReader


@pytest.fixture
def fake_server():
    """OpenAI uslubidagi /v1/chat/completions — kelgan so'rovni saqlaydi, tayyor javob qaytaradi."""
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802 — http.server nomi
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = json.dumps({"choices": [{"message": {"content": " 12.03.2026 № 55/07 \n"}}]})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):  # testda konsolga yozmasin
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/v1/chat/completions", received
    server.shutdown()


def png(width: int, height: int) -> bytes:
    return cv2.imencode(".png", np.full((height, width, 3), 255, np.uint8))[1].tobytes()


def test_request_shape_and_answer(fake_server):
    url, received = fake_server
    assert VlmReader(url).read(png(3000, 1000)) == "12.03.2026 № 55/07"
    request = received[0]
    assert request["temperature"] == 0
    image_part, text_part = request["messages"][0]["content"]
    assert "Do not correct" in text_part["text"]
    data = image_part["image_url"]["url"].removeprefix("data:image/png;base64,")
    image = cv2.imdecode(np.frombuffer(base64.b64decode(data), np.uint8), cv2.IMREAD_COLOR)
    assert max(image.shape[:2]) == MAX_SIDE  # katta bo'lak kichraytirildi


def test_only_local_server_is_allowed():
    with pytest.raises(ValueError):
        VlmReader("https://example.com/v1/chat/completions")


def test_extract_mode_asks_for_json(fake_server):
    url, received = fake_server
    VlmReader(url, mode="extract").read(png(100, 100))
    question = received[0]["messages"][0]["content"][1]["text"]
    assert '"sana"' in question and "На №" in question  # JSON so'raladi, "На №" chetlanadi
