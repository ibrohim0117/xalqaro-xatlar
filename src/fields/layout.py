"""1-sahifa tuzilishi: sarlavha qayergacha va o'ng yuqori blok (qabul qiluvchi).

Boshqarma, jo'natuvchi va uning variantlari — uchalasi ham shu chegaralardan foydalanadi.
"""

from src.reading.pages import CachedPage
from src.reading.pdf_text import Word

RIGHT_BLOCK_X = 0.45  # o'ng yarmi: qabul qiluvchi bloki shu yerda
HEADER_FALLBACK_Y = 0.40  # "№" topilmasa — sarlavha shu balandlikkacha deb olinadi
ANCHOR_MARGIN = 0.03  # "№" qatoridan biroz pastgacha


def header_bottom(first: CachedPage) -> float:
    """Sarlavha qayergacha: eng yuqoridagi "№" (sana-raqam qatori) dan biroz pastgacha.
    "№" ni OCR yaxshiroq topadi, shuning uchun ikkala manbaga ham qaraladi."""
    words = first.text_layer.words + (first.ocr.words if first.ocr else [])
    ys = [w.y0 for w in words if "№" in w.text and w.y0 < 0.5]
    return min(ys) + ANCHOR_MARGIN if ys else HEADER_FALLBACK_Y


def in_recipient_block(word: Word, bottom: float) -> bool:
    return word.x0 >= RIGHT_BLOCK_X and word.y0 < bottom


def sender_block(first: CachedPage) -> list[Word]:
    """Chap yuqori blok (jo'natuvchi blanki): o'ng blokdan tashqari, "№" qatoridan yuqorida."""
    top = header_bottom(first) - ANCHOR_MARGIN  # "№" qatorining o'zi (topilmasa — zaxira chegara)
    return [w for w in first.main.words if w.y0 < top and w.x0 < RIGHT_BLOCK_X]
