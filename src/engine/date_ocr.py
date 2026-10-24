"""B5.3c: sana — bitta xat uchun qo'lyozma OCR: bo'laklar -> OCR'lar -> ovoz -> natija.

Natija (B5.3b o'lchovlari, dev 70, oyna 365 kun):
  - auto: matn qatlamidan olingan sana — 13/13 (100%); bunda OCR umuman ishlamaydi;
  - prefill (fields/date_vote.prefill_date): VLM aniq savol bilan header'dan topgan sana, boshqa OCR
    tasdiqlagan — 32/34 (B5.3c-8, X2): maydonga yoziladi, lekin "tekshirish kerak" belgisi bilan
    (sezdirmasdan yozilgan xato sana bo'lmasin). Topuvchi — birinchi ISHLAGAN OCR: aniq savol
    ishlamasa — VLM ko'chirish (27/28); VLM umuman bo'lmasa — date bo'laklaridan kamida 2 OCR
    kelishgan sana (VLM'siz o'lchov: 18/18);
  - suggestions: ko'proq OCR ko'rgan 3 ta sana — xodim bir bosishda tanlaydi.
Biror OCR ishlamasa (masalan, VLM serveri o'chiq) — shu xat uchun chetlanadi, qolganlari ishlaydi.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date as Date

import pymupdf

from src.engine.locate import ocr_regions
from src.fields.date_number import date_and_number
from src.fields.date_vote import (
    WINDOW_DAYS,
    engine_dates,
    in_window,
    prefill_date,
    ranked,
    windowed,
)
from src.reading.crops import crop_png, dpi_for
from src.reading.engines import LineReader, make_reader
from src.reading.pages import CachedPage

CROPS = ("date", "line", "header")  # sana uchun kerakli bo'laklar
# Aniq savol: header — topuvchi sana (X2, 46/65); page va line — faqat takliflar uchun (dev 70:
# to'g'ri sana takliflarda 9 -> 14), yozish qoidasiga kirmaydi (VLM o'zini o'zi tasdiqlashi
# ishonchsiz, X3)
READER_CROPS = {"vlm-extract": ("header", "page", "line")}
# Qaysi OCR'lar (tartib muhim: 1-si topuvchi bo'lsa — "biri topadi, boshqasi tasdiqlaydi")
DEFAULT_READERS = "vlm-extract,vlm,rapidocr,rapidocr-eslav,tesseract-block"
log = logging.getLogger(__name__)


@dataclass
class DateReading:
    auto: str | None = None  # avtomatik (ishonchli)
    prefill: str | None = None  # yoziladi, lekin "tekshiring"
    suggestions: list[str] = field(default_factory=list)  # 3 tagacha taklif
    seconds: float = 0.0  # OCR'ga ketgan vaqt
    readers: list[str] = field(default_factory=list)  # ishlagan OCR'lar


def crops_for(reader: str) -> tuple[str, ...]:
    """Bu OCR sana uchun qaysi bo'laklarni o'qiydi (o'lchov ham shu bilan — date_failures)."""
    return READER_CROPS.get(reader, CROPS)


class DateOcr:
    def __init__(self, readers: list[LineReader]):
        self.readers = readers

    def read(self, page: pymupdf.Page, first: CachedPage, received: Date) -> DateReading:
        auto = date_and_number(first.text_layer)[0]
        if in_window(auto, received, WINDOW_DAYS):
            return DateReading(auto=auto)
        start = time.perf_counter()
        regions = ocr_regions(first)
        wanted = {name for reader in self.readers for name in crops_for(reader.name)}
        crops = {
            name: crop_png(page, box, dpi=dpi_for(name))
            for name, box in regions.items()
            if name in wanted
        }
        found, worked = [], []
        for reader in self.readers:
            # bitta OCR ishlamasa (masalan, VLM serveri o'chiq) — chetlanadi, qolganlari davom etadi
            try:
                texts = {
                    name: reader.read(png)
                    for name, png in crops.items()
                    if name in crops_for(reader.name)
                }
            except Exception as error:
                log.warning("%s ishlamadi: %s", reader.name, error)
                continue
            found.append(windowed(engine_dates(texts), received))
            worked.append(reader.name)
        prefill = prefill_date(found, worked[0] if worked else None)
        suggestions = ranked([{d for d in f.values() if d} for f in found])
        return DateReading(None, prefill, suggestions, time.perf_counter() - start, worked)


def build_date_ocr(names: str | None = None) -> DateOcr | None:
    """SANA_OCR (vergul bilan) dagi OCR'lar; bo'sh — sana OCR'i o'chiq. Yuklanmagan yoki serveri
    javob bermagan OCR (masalan, VLM) ogohlantirish bilan chetlanadi."""
    names = os.environ.get("SANA_OCR", DEFAULT_READERS) if names is None else names
    readers = []
    for name in filter(None, (n.strip() for n in names.split(","))):
        try:
            reader = make_reader(name)
        except Exception as error:  # model fayli yo'q va h.k.
            log.warning("%s yuklanmadi: %s", name, error)
            continue
        if hasattr(reader, "available") and not reader.available():
            log.warning("%s serveri javob bermadi — chetlandi", name)
            continue
        readers.append(reader)
    if not readers:
        return None
    return DateOcr(readers)


def apply_reading(answer: dict, reading: DateReading) -> None:
    """Natijani javobga qo'shadi: auto — yoziladi; prefill — yoziladi, "tekshirish kerak" qoladi;
    takliflar — ro'yxat (predict'ning bitta taklifi o'rniga)."""
    rekvizit, flags = answer["rekvizit_document"], answer["tekshirish_kerak"]
    if reading.auto:
        rekvizit["hujjat_sana"] = reading.auto
        if "hujjat_sana" in flags:
            flags.remove("hujjat_sana")
    elif reading.prefill:
        rekvizit["hujjat_sana"] = reading.prefill
        if "hujjat_sana" not in flags:
            flags.append("hujjat_sana")
    if reading.suggestions:
        answer["takliflar"]["hujjat_sana"] = reading.suggestions
