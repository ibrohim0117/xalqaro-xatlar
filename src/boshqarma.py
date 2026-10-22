"""B4: xat matnidan boshqarmani aniqlash.

B4.2 — hudud: qabul qiluvchi blokini (1-sahifa, o'ng yuqori) va vazirlik manzilini chetlab,
qolgan matndagi hudud eslatmalari og'irligi bo'yicha eng kuchli hudud tanlanadi.
"""

import re
from collections import defaultdict

from src.pdf_text import PageText, Word
from src.regions import Hit, find_regions, prepare
from src.text_cache import CachedPage

RIGHT_BLOCK_X = 0.45  # o'ng yarmi: qabul qiluvchi bloki shu yerda
HEADER_FALLBACK_Y = 0.40  # "№" topilmasa — sarlavha shu balandlikkacha deb olinadi
ANCHOR_MARGIN = 0.03  # "№" qatoridan biroz pastgacha
# Vazirlikning o'z manzili: "... юстиции Республики Узбекистан ... г. Ташкент, ул. Сайилгох, 5"
MINISTRY = re.compile(r"юстиции\s+республики\s+узбекистан")
MINISTRY_STREET = re.compile(r"са[йи]{1,2}лго[хx]")


def header_bottom(first: CachedPage) -> float:
    """Sarlavha qayergacha: eng yuqoridagi "№" (sana-raqam qatori) dan biroz pastgacha.
    "№" ni OCR yaxshiroq topadi, shuning uchun ikkala manbaga ham qaraladi."""
    words = first.text_layer.words + (first.ocr.words if first.ocr else [])
    ys = [w.y0 for w in words if "№" in w.text and w.y0 < 0.5]
    return min(ys) + ANCHOR_MARGIN if ys else HEADER_FALLBACK_Y


def in_recipient_block(word: Word, bottom: float) -> bool:
    return word.x0 >= RIGHT_BLOCK_X and word.y0 < bottom


def region_text(
    pages: list[CachedPage], max_pages: int | None = None, drop_recipient: bool = True
) -> str:
    """Hudud qidiriladigan matn. 1-sahifada qabul qiluvchi bloki chiqarib tashlanadi."""
    parts = []
    for page in pages[:max_pages]:
        main = page.main
        if drop_recipient and page.number == 1:
            bottom = header_bottom(page)
            kept = [w for w in main.words if not in_recipient_block(w, bottom)]
            main = PageText(main.number, main.source, kept)
        parts.append(main.text)
    return "\n".join(parts)


def is_ministry_address(low: str, hit: Hit) -> bool:
    """Toshkent eslatmasi vazirlikning o'z manzilimi (xat matni ichida kelgan bo'lsa ham)."""
    if hit.key != "toshkent_sh":
        return False
    before = low[max(0, hit.start - 120) : hit.start]
    around = low[max(0, hit.start - 60) : hit.end + 60]
    return bool(MINISTRY.search(before) or MINISTRY_STREET.search(around))


def letter_regions(text: str, drop_ministry: bool = True) -> list[Hit]:
    low = prepare(text)
    hits = find_regions(low)
    if drop_ministry:
        hits = [h for h in hits if not is_ministry_address(low, h)]
    return hits


def choose_region(hits: list[Hit]) -> str | None:
    """Og'irliklar yig'indisi eng katta hudud; teng bo'lsa — matnda birinchi uchragani."""
    if not hits:
        return None
    score: dict[str, int] = defaultdict(int)
    first: dict[str, int] = {}
    for hit in hits:
        score[hit.key] += hit.weight
        first.setdefault(hit.key, hit.start)
    return max(score, key=lambda key: (score[key], -first[key]))
