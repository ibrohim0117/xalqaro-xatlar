"""B5.3b: OCR'lar uchun yagona ko'rinish — rasm bo'lagi (PNG) kiradi, matn chiqadi.

Har OCR alohida faylda; og'ir kutubxonalar (torch, mlx …) faqat o'sha OCR tanlanganda yuklanadi.
Yangi OCR qo'shish — bitta fayl va READERS ga bitta qator.
"""

import importlib
from typing import Protocol


class LineReader(Protocol):
    name: str

    def read(self, png: bytes) -> str: ...


# nom -> (modul, sinf, sozlamalar)
READERS: dict[str, tuple[str, str, dict]] = {
    "tesseract": ("src.reading.engines.tesseract", "TesseractReader", {}),
    "tesseract-bin": ("src.reading.engines.tesseract", "TesseractReader", {"binary": True}),
    "tesseract-digits": ("src.reading.engines.tesseract", "TesseractReader", {"digits_only": True}),
    "tesseract-block": ("src.reading.engines.tesseract", "TesseractReader", {"psm": 6}),
    "tesseract-sparse": ("src.reading.engines.tesseract", "TesseractReader", {"psm": 11}),
    "rapidocr": ("src.reading.engines.rapid", "RapidReader", {}),
    "rapidocr-eslav": ("src.reading.engines.rapid", "RapidReader", {"rec": "eslav"}),
    "vlm": ("src.reading.engines.vlm", "VlmReader", {}),  # server: scripts/ocr/vlm_server.sh
    # aniq savol: sana va raqam JSON'da; butun sahifa uchun kattaroq rasm
    "vlm-extract": (
        "src.reading.engines.vlm",
        "VlmReader",
        {"mode": "extract", "max_side": 1600},
    ),
    # sinov (B5.5-4): o'sha savol, 4B model — server: VLM_MODEL=models/vlm/Qwen3.5-4B-4bit
    "vlm-extract-4b": (
        "src.reading.engines.vlm",
        "VlmReader",
        {"mode": "extract", "max_side": 1600, "model": "models/vlm/Qwen3.5-4B-4bit"},
    ),
    "tesseract-digits-block": (
        "src.reading.engines.tesseract",
        "TesseractReader",
        {"digits_only": True, "psm": 6},
    ),
}


def make_reader(name: str) -> LineReader:
    module, cls, options = READERS[name]
    reader = getattr(importlib.import_module(module), cls)(**options)
    reader.name = name
    return reader
