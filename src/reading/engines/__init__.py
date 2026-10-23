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
