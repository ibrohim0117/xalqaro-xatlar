"""B5.3c: sana — bitta xat uchun qo'lyozma OCR: bo'laklar -> OCR'lar -> ovoz -> natija.

Natija (B5.3b o'lchovlari, dev 70, oyna 365 kun):
  - auto: matn qatlamidan olingan sana — 13/13 (100%); B5.12: OCR baribir ishlaydi, lekin faqat
    raqam uchun (bunday xatlarda ham raqam ko'pincha qo'lda: dev 13 xatda raqam 0 -> 7 to'g'ri
    yozildi, 2 xato ⚠ bilan; vaqt shu xatlarga ~+38 s); sana takliflari bo'lmaydi;
  - prefill (fields/date_vote.prefill_date): VLM aniq savol bilan header'dan topgan sana, boshqa OCR
    tasdiqlagan — 32/34 (B5.3c-8, X2): maydonga yoziladi, lekin "tekshirish kerak" belgisi bilan
    (sezdirmasdan yozilgan xato sana bo'lmasin). Topuvchi — birinchi ISHLAGAN OCR: aniq savol
    ishlamasa — VLM ko'chirish (27/28); VLM umuman bo'lmasa — date bo'laklaridan kamida 2 OCR
    kelishgan sana (VLM'siz o'lchov: 18/18);
  - suggestions: ko'proq OCR ko'rgan 3 ta sana — xodim bir bosishda tanlaydi.
B5.11 yil tuzatish va B5.14 Apple Vision bilan (dev 70): sana to'g'ri 54, xato 2, bir bosishda 63.
Biror OCR ishlamasa (masalan, VLM serveri o'chiq) — shu xat uchun chetlanadi, qolganlari ishlaydi.
"""

import logging
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date as Date

import pymupdf

from src.engine.locate import fixed_regions, ocr_regions
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
READER_CROPS = {
    "vlm-extract": ("header", "page", "line"),
    # B5.14: Apple Vision tez (bo'lakka ~0.15 s) — raqam bo'lagi (dev: 16/70, VLM header 22) va
    # butun sahifa ham o'qiladi
    "apple-vision": ("date", "line", "header", "number", "page"),
}
# Qaysi OCR'lar (tartib muhim: 1-si topuvchi bo'lsa — "biri topadi, boshqasi tasdiqlaydi")
# B5.14: apple-vision (macOS'ning o'z OCR'i, oflayn, ~1 s/xat) — tasdiqlovchi; dev 70: sana
# 53 -> 54, raqam to'g'ri 18 -> 23, xato 3 -> 6 (⚠ bilan), bir bosishda 40 o'zgarmadi.
# macOS bo'lmasa — chetlanadi (build_date_ocr ogohlantiradi)
DEFAULT_READERS = "vlm-extract,vlm,rapidocr,rapidocr-eslav,tesseract-block,apple-vision"
log = logging.getLogger(__name__)


@dataclass
class DateReading:
    auto: str | None = None  # avtomatik (ishonchli)
    prefill: str | None = None  # yoziladi, lekin "tekshiring"
    suggestions: list[str] = field(default_factory=list)  # 3 tagacha taklif
    seconds: float = 0.0  # OCR'ga ketgan vaqt
    readers: list[str] = field(default_factory=list)  # ishlagan OCR'lar
    # OCR -> bo'lak -> o'qilgan matn (raqam ham shundan olinadi — qayta OCR'siz)
    texts: dict[str, dict[str, str]] = field(default_factory=dict)


def crops_for(reader: str) -> tuple[str, ...]:
    """Bu OCR sana uchun qaysi bo'laklarni o'qiydi (o'lchov ham shu bilan — date_failures)."""
    return READER_CROPS.get(reader, CROPS)


def lane_of(reader: str) -> str:
    """Yo'lak: VLM alohida jarayonda (server) ishlaydi — bizning kod faqat javobini kutadi; qolgan
    OCR'lar shu protsessorda. Ikki yo'lak bir vaqtda ishlaydi (vaqt o'lchovi, real 10 xat: VLM
    ~32.6 s, qolgan OCR'lar ~5.1 s — ular VLM'ni kutish ichiga kiradi). Yo'lak ichida tartib
    o'sha: VLM serveriga bir vaqtda bitta so'rov (8 GB xotira)."""
    return "vlm" if reader.startswith("vlm") else "cpu"


EARLY_LANE = "vlm"  # sahifa OCR'idan oldin boshlanadigan yo'lak (EarlyReading)
Pairs = list[
    tuple[LineReader, dict[str, str] | None]
]  # OCR va uning bo'lak matnlari (None — ishlamadi)


def read_queue(
    readers: list[LineReader],
    fixed: dict[str, bytes],
    rest: Callable[[], dict[str, bytes] | None],
) -> Pairs:
    """Bitta yo'lakdagi OCR'lar ketma-ket. Har biri avval o'zgarmas bo'laklarini (fixed: header,
    page) o'qiydi, keyin "№" qatori bo'laklarini — rest() beradi (kerak bo'lsa kutadi). Tartib
    ocr_regions'dagidek (fixed u yerda ham birinchi). rest() None — zanjir to'xtadi, navbat tugaydi.
    Biror OCR ishlamasa (masalan, VLM serveri o'chiq) — None, qolganlari davom etadi."""
    out: Pairs = []
    for reader in readers:
        wanted = crops_for(reader.name)
        try:
            texts = {name: reader.read(png) for name, png in fixed.items() if name in wanted}
            if any(name not in fixed for name in wanted):
                crops = rest()
                if crops is None:
                    return out
                texts |= {
                    name: reader.read(png)
                    for name, png in crops.items()
                    if name in wanted and name not in fixed
                }
        except Exception as error:
            log.warning("%s ishlamadi: %s", reader.name, error)
            texts = None
        out.append((reader, texts))
    return out


class EarlyReading:
    """VLM yo'lagi sahifa OCR'idan OLDIN boshlanadi: header va page ("№" ga bog'liq emas) darhol
    o'qiladi, "№" qatori bo'laklari Tesseract 1-sahifani o'qigach beriladi (finish). VLM serveriga
    so'rovlar tartibi o'sha — faqat ertaroq boshlanadi. Kesish (PyMuPDF) doim asosiy oqimda, orqa
    fonda faqat tayyor PNG baytlari o'qiladi. Vaqt o'lchovi (real 10 xat): sahifa OCR o'rtacha
    3.4 s — VLM'ni kutish ichiga kiradi."""

    def __init__(self, readers: list[LineReader], fixed: dict[str, bytes], started: float):
        self.fixed, self.started = fixed, started
        self._ready, self._crops = threading.Event(), None
        pool = ThreadPoolExecutor(max_workers=1)
        self.job = pool.submit(read_queue, readers, fixed, self._rest)
        pool.shutdown(wait=False)

    def _rest(self) -> dict[str, bytes] | None:
        self._ready.wait()
        return self._crops

    def finish(self, crops: dict[str, bytes]) -> Pairs:
        """Hamma bo'laklar beriladi; navbat tugashini kutadi."""
        self._crops = crops
        self._ready.set()
        return self.job.result()

    def abandon(self) -> None:
        """Zanjir xato bilan to'xtasa: navbat qolgan bo'laklarni kutmasdan tugaydi (osilib
        qolmaydi). finish'dan keyin chaqirilsa — hech narsa qilmaydi."""
        self._ready.set()


class DateOcr:
    def __init__(self, readers: list[LineReader]):
        self.readers = readers

    def reader(self, name: str) -> LineReader | None:
        """Shu nomdagi OCR (masalan, imzo uchun Apple Vision) — yuklangan bo'lsa."""
        return next((r for r in self.readers if r.name == name), None)

    def _wanted(self) -> set[str]:
        return {name for reader in self.readers for name in crops_for(reader.name)}

    def start(self, page: pymupdf.Page) -> EarlyReading:
        """Sahifa OCR'idan oldin (pipeline): header va page kesiladi, VLM o'qiy boshlaydi."""
        started = time.perf_counter()
        wanted = self._wanted()
        fixed = {
            name: crop_png(page, box, dpi=dpi_for(name))
            for name, box in fixed_regions().items()
            if name in wanted
        }
        early = [reader for reader in self.readers if lane_of(reader.name) == EARLY_LANE]
        return EarlyReading(early, fixed, started)

    def read(
        self,
        page: pymupdf.Page,
        first: CachedPage,
        received: Date,
        early: EarlyReading | None = None,
    ) -> DateReading:
        """early — pipeline sahifa OCR'idan oldin boshlagan VLM yo'lagi; berilmasa — shu yerda."""
        auto = date_and_number(first.text_layer)[0]
        auto = auto if in_window(auto, received, WINDOW_DAYS) else None
        early = early or self.start(page)
        try:
            wanted = self._wanted()
            crops = {
                name: early.fixed[name]
                if name in early.fixed
                else crop_png(page, box, dpi=dpi_for(name))
                for name, box in ocr_regions(first).items()
                if name in wanted
            }
            lanes: dict[str, list[LineReader]] = {}
            for reader in self.readers:
                if lane_of(reader.name) != EARLY_LANE:
                    lanes.setdefault(lane_of(reader.name), []).append(reader)
            with ThreadPoolExecutor(max_workers=len(lanes) or 1) as pool:
                jobs = [
                    pool.submit(read_queue, readers, {}, lambda: crops)
                    for readers in lanes.values()
                ]
                pairs = early.finish(crops) + [pair for job in jobs for pair in job.result()]
        finally:
            early.abandon()
        results = dict(pairs)
        found, worked, read = [], [], {}
        for reader in self.readers:  # natijalar avvalgi tartibda: 1-ishlagan OCR — topuvchi
            texts = results[reader]
            if texts is None:
                continue
            found.append(windowed(engine_dates(texts), received))
            worked.append(reader.name)
            read[reader.name] = texts
        seconds = (
            time.perf_counter() - early.started
        )  # sahifa OCR'i bilan ustma-ust bo'lishi mumkin
        if auto:  # sana bosma — OCR matnlari faqat raqam uchun (B5.12)
            return DateReading(auto=auto, seconds=seconds, readers=worked, texts=read)
        prefill = prefill_date(found, worked[0] if worked else None)
        suggestions = ranked([{d for d in f.values() if d} for f in found])
        return DateReading(None, prefill, suggestions, seconds, worked, read)


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
