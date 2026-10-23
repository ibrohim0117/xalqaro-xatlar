"""Tesseract — bo'lakdagi qatorni o'qish (asos: hozirgi tizim shu bilan ishlaydi)."""

import cv2
import numpy as np
import pytesseract

from src.reading.pdf_text import TESS_CONFIG, binarize

DIGITS = "0123456789./-№"  # sana va raqamda boshqa belgi yo'q — "Я" kabi axlat chiqmasin


class TesseractReader:
    name = "tesseract"

    def __init__(
        self, lang: str = "rus", binary: bool = False, digits_only: bool = False, psm: int = 7
    ):
        self.lang = lang
        self.binary = binary  # avval oq-qora (butun sahifa OCR'idagidek)
        # psm: 7 — bitta qator, 6 — bir necha qatorli blok, 11 — sochilgan matn (qatorga qaramaydi)
        self.config = f"{TESS_CONFIG} --psm {psm}"
        if digits_only:
            self.config += f" -c tessedit_char_whitelist={DIGITS}"

    def read(self, png: bytes) -> str:
        gray = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
        if self.binary:
            gray = binarize(gray)
        return pytesseract.image_to_string(gray, lang=self.lang, config=self.config).strip()
