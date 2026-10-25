"""B5.15: imzo — PDF matni buzilgan yoki imzo topilmagan bo'lsa, Apple Vision o'qiydi.

Matn qoidasi (fields/signer.find_signer) imzo topmasa yoki topgani buzilgan bo'lsa (birinchi bosh
harf PDF matnida yo'qolgan — ".Б. Сидоров", Candidate.damaged), Vision 1-sahifaning pastki yarmini
rasm sifatida o'qiydi va o'sha qoida Vision so'zlariga qo'llanadi.
O'lchov (scripts/rekvizit/vision_signers, V2; dev 70; B6 testi yopiq): imzo to'g'ri 59 -> 62,
xato 5 -> 2, to'g'ri -> xato 0 (bosh harfi yo'qolgan 3 ta imzoning 3 tasi tuzaldi; imzo topilmagan
6 xatga yordam bermadi — imzo 2–3-sahifada). Vision bo'lmasa (macOS emas) — o'zgarishsiz.
"""

import logging

import pymupdf

from src.fields.signer import Candidate, find_signer
from src.reading.crops import crop_png
from src.reading.engines import LineReader
from src.reading.engines.vision import to_words
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText

VISION = "apple-vision"
REGION = (0.0, 0.5, 1.0, 1.0)  # 1-sahifaning pastki yarmi (imzo qoidasi ham shu yerda qidiradi)
DPI = 300
log = logging.getLogger(__name__)


def needs_vision(current: Candidate | None) -> bool:
    """Matn qoidasi imzo topmadi yoki topgani buzilgan."""
    return current is None or current.damaged


def vision_signer(page: pymupdf.Page, reader: LineReader) -> Candidate | None:
    """1-sahifaning pastki yarmi Vision bilan -> o'sha imzo qoidasi."""
    box = dict(zip(("x0", "y0", "x1", "y1"), REGION, strict=True))
    png = crop_png(page, box, dpi=DPI, pad=0.0)
    words = to_words(reader.observations(png), REGION)
    return find_signer([CachedPage(1, PageText(1, "ocr", words), None)])


def vision_fallback(
    page: pymupdf.Page, pages: list[CachedPage], reader: LineReader | None
) -> tuple[Candidate, bool] | None:
    """Kerak bo'lsa Vision imzosi va u buzilgan imzoni TUZATDIMI (matn qoidasi biror imzo topgan
    edi). Vision yo'q, kerak emas, ishlamadi yoki topmadi — None."""
    current = find_signer(pages)
    if reader is None or not needs_vision(current):
        return None
    try:
        found = vision_signer(page, reader)
    except Exception as error:  # Vision ishlamasa — matn qoidasi natijasi qoladi
        log.warning("Vision imzoni o'qimadi: %s", error)
        return None
    return (found, current is not None) if found else None


def apply_signer(answer: dict, signer: Candidate, repaired: bool) -> None:
    """Vision imzosi yoziladi. Buzilgan imzoni tuzatgan bo'lsa (dev 3/3) — "tekshirish kerak"
    olib tashlanadi; matn qoidasi umuman topmagan imzo (dev'da bunday holat bo'lmadi) yoki yana
    buzilgan bo'lsa — belgi qoladi."""
    answer["rekvizit_document"]["imzolagan_shaxs"] = signer.latin()
    flags = answer["tekshirish_kerak"]
    trusted = repaired and not signer.damaged
    if trusted and "imzolagan_shaxs" in flags:
        flags.remove("imzolagan_shaxs")
    elif not trusted and "imzolagan_shaxs" not in flags:
        flags.append("imzolagan_shaxs")
