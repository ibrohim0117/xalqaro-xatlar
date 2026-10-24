"""VLM (rasmni ko'radigan til modeli, Qwen3.5-2B) — lokal serverga OpenAI uslubidagi so'rov.

Server alohida muhitda ishlaydi (scripts/ocr/vlm_server.sh: mlx-vlm, faqat 127.0.0.1, oflayn).
Bizning kod faqat manzil bilan gaplashadi: ertaga Linux serverda xuddi shu model llama.cpp yoki
vLLM bilan ishga tushirilsa — bu fayl o'zgarmaydi. So'rov Python'ning o'z urllib'i bilan.
MAXFIYLIK: faqat lokal manzil qabul qilinadi (xat kompyuterdan chiqmasin).
"""

import base64
import json
import os
import urllib.request

import cv2
import numpy as np

VLM_URL = os.environ.get("VLM_URL", "http://127.0.0.1:8090/v1/chat/completions")
MODEL = "models/vlm/Qwen3.5-2B-4bit"  # server yuklagan model (boshqa nom — serverda qayta yuklash)
LOCAL = ("http://127.0.0.1:", "http://localhost:")
MAX_SIDE = 1280  # katta bo'lak (header) kichraytiriladi: kamroq vizual token — tezroq
TRANSCRIBE = (
    "Transcribe all text in this image exactly as written, line by line, including handwritten "
    "dates and numbers. Do not correct, complete or guess anything. If a part is unreadable, "
    "skip it. Output only the transcribed text."
)
# Aniq savol: xatning O'Z sanasi va chiqish raqami (javob — JSON; parse_date/parse_number o'qiydi).
# "На № … от …" — bizning oldingi xatimiz sanasi, u kerak emas.
EXTRACT = (
    "This image is (part of) an official letter. Find the letter's OWN date and outgoing number. "
    "They are usually written together on one line like '<date> № <number>', often by hand or "
    "with a stamp. Do NOT use the reference line 'На № ... от ...' (a reply to another letter), "
    "dates of birth or other dates in the text. Read digits exactly as written; do not guess. "
    'Answer only JSON: {"sana": "DD.MM.YYYY" or null, "raqam": "<number>" or null}'
)
PROMPTS = {"transcribe": TRANSCRIBE, "extract": EXTRACT}


class VlmReader:
    name = "vlm"

    def __init__(
        self,
        url: str = VLM_URL,
        mode: str = "transcribe",
        timeout: float = 300,
        max_side: int = MAX_SIDE,
    ):
        """mode: "transcribe" — matnni ko'chiradi; "extract" — xatning sanasi va raqami (JSON)."""
        if not url.startswith(LOCAL):
            raise ValueError(f"VLM faqat lokal manzilda bo'lishi kerak: {url}")
        self.url, self.prompt, self.timeout, self.max_side = url, PROMPTS[mode], timeout, max_side

    def available(self) -> bool:
        """Server javob beryaptimi (/health). Yoqilmagan bo'lsa — VLM chetlanadi."""
        health = self.url.split("/v1/")[0] + "/health"
        try:
            with urllib.request.urlopen(health, timeout=2) as response:
                return response.status == 200
        except OSError:
            return False

    def read(self, png: bytes) -> str:
        image = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        scale = self.max_side / max(image.shape[:2])
        if scale < 1:
            image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        encoded = base64.b64encode(cv2.imencode(".png", image)[1].tobytes()).decode()
        image_part = {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}
        body = {
            "model": MODEL,
            "messages": [
                {"role": "user", "content": [image_part, {"type": "text", "text": self.prompt}]}
            ],
            "temperature": 0,  # har safar bir xil javob, "ijod" yo'q
            "max_tokens": 300,
        }
        request = urllib.request.Request(
            self.url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            answer = json.load(response)
        return (answer["choices"][0]["message"]["content"] or "").strip()
