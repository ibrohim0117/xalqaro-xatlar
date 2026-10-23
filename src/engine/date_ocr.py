"""B5.3c: sana — bitta xat uchun qo'lyozma OCR: bo'laklar -> OCR'lar -> ovoz -> natija.

Natija (B5.3b o'lchovlari, dev 70, oyna 365 kun):
  - auto: matn qatlamidan olingan sana — 13/13 (100%); bunda OCR umuman ishlamaydi;
  - prefill: 1-OCR (VLM) sanasi, boshqa OCR tasdiqlagan — 27/28 (96%): maydonga yoziladi, lekin
    "tekshirish kerak" belgisi bilan (sezdirmasdan yozilgan xato sana bo'lmasin);
    VLM bo'lmasa — date bo'laklaridan kamida 2 OCR kelishgan sana (VLM'siz o'lchov: 18/18);
  - suggestions: ko'proq OCR ko'rgan 3 ta sana — xodim bir bosishda tanlaydi.
Biror OCR ishlamasa (masalan, VLM serveri o'chiq) — shu xat uchun chetlanadi, qolganlari ishlaydi.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import date as Date

import pymupdf

from src.engine.locate import ocr_regions
from src.fields.date_number import date_and_number
from src.fields.date_vote import (
    WINDOW_DAYS,
    confirmed,
    engine_dates,
    in_window,
    ranked,
    vote,
    windowed,
)
from src.reading.crops import crop_png
from src.reading.engines import LineReader
from src.reading.pages import CachedPage

CROPS = ("date", "line", "header")  # sana uchun kerakli bo'laklar
log = logging.getLogger(__name__)


@dataclass
class DateReading:
    auto: str | None = None  # avtomatik (ishonchli)
    prefill: str | None = None  # yoziladi, lekin "tekshiring"
    suggestions: list[str] = field(default_factory=list)  # 3 tagacha taklif
    seconds: float = 0.0  # OCR'ga ketgan vaqt
    readers: list[str] = field(default_factory=list)  # ishlagan OCR'lar


class DateOcr:
    def __init__(self, readers: list[LineReader], confirm_first: bool):
        """confirm_first: 1-OCR (VLM) topadi, boshqasi tasdiqlaydi; aks holda — oddiy ovoz."""
        self.readers = readers
        self.confirm_first = confirm_first

    def read(self, page: pymupdf.Page, first: CachedPage, received: Date) -> DateReading:
        auto = date_and_number(first.text_layer)[0]
        if in_window(auto, received, WINDOW_DAYS):
            return DateReading(auto=auto)
        start = time.perf_counter()
        regions = ocr_regions(first)
        crops = {name: crop_png(page, regions[name]) for name in CROPS if name in regions}
        found, worked = [], []
        for reader in self.readers:
            # bitta OCR ishlamasa (masalan, VLM serveri o'chiq) — chetlanadi, qolganlari davom etadi
            try:
                texts = {name: reader.read(png) for name, png in crops.items()}
            except Exception as error:
                log.warning("%s ishlamadi: %s", reader.name, error)
                continue
            found.append(windowed(engine_dates(texts), received))
            worked.append(reader.name)
        if self.confirm_first and worked[:1] == [self.readers[0].name]:
            prefill = confirmed(found)
        else:
            prefill = vote([{f["date"]} - {None} for f in found])
        suggestions = ranked([{d for d in f.values() if d} for f in found])
        return DateReading(None, prefill, suggestions, time.perf_counter() - start, worked)
