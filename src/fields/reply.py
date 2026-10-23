"""B5.4: javob xat — "На № <raqam> от <sana>" qatori: xat BIZNING oldingi xatimizga javob.

Bunday xatlarning qisqacha mazmuni xodimlar yozgan json'da "<sana>-yildagi <raqam>-son xat ijrosi
bo'yicha" shaklida (Ibrohim ko'rgan dev xat); boshqarmani raqam boshidagi indeksdan bilish mumkin
(Ulug'bek: 15 ta javob xatda 15/15). date_number "На №" ni tuzoq deb o'tkazib yuboradi — bu modul
aynan o'sha qatorni o'qiydi.

Langar: "№", undan oldin o'sha qatorda (3 so'z ichida) "на" — "На №", "На Ваш №", "на исх. №".
"""

import re

from src.fields.date_number import (
    ANCHOR,
    ANCHOR_MAX_Y,
    NUMBER,
    SAME_LINE,
    TRAP_BEFORE,
    is_date_token,
    parse_date,
)
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText, Word

LOOK_BACK = 3  # "№" dan oldin shuncha so'z ichida "на" bo'lsa — javob qatori
JOINED = re.compile(r"^на№", re.IGNORECASE)  # "На№17/08-10/2934" — bo'shliqsiz yozilgan
TEMPLATE = "{date}-yildagi {number}-son xat ijrosi bo'yicha"


def is_reply_anchor(words: list[Word], i: int) -> bool:
    word = words[i]
    if word.y0 >= ANCHOR_MAX_Y:
        return False
    if JOINED.match(word.text):
        return True
    if not ANCHOR.match(word.text):
        return False
    before = [w for w in words[max(0, i - LOOK_BACK) : i] if w.line == word.line]
    return any(TRAP_BEFORE.match(w.text.strip(".,")) for w in before)


def find_reply_anchor(page: PageText) -> Word | None:
    """ "На №" dagi "№" (eng yuqoridagisi)."""
    found = [w for i, w in enumerate(page.words) if is_reply_anchor(page.words, i)]
    return min(found, key=lambda w: w.y0, default=None)


def reply_anchor_of(first: CachedPage) -> Word | None:
    """Joyini ko'rsatish/kesish uchun: avval matn qatlami, keyin OCR."""
    pages = (p for p in (first.text_layer, first.ocr) if p is not None)
    return next((a for p in pages if (a := find_reply_anchor(p)) is not None), None)


def reply_reference(page: PageText) -> tuple[str | None, str | None] | None:
    """(raqam, sana) "На №" qatoridan. Qator yo'q — None; bor, lekin bo'sh ("На № ___ от ___")
    yoki qo'lda yozilgani o'qilmagan — (None, None)."""
    anchor = find_reply_anchor(page)
    if anchor is None:
        return None
    after = sorted(
        (w for w in page.words if abs(w.y0 - anchor.y0) <= SAME_LINE and w.x0 > anchor.x0),
        key=lambda w: w.x0,
    )
    tokens = [JOINED.sub("", ANCHOR.sub("", anchor.text))] + [w.text for w in after]
    number = None
    for k, token in enumerate(tokens):
        if token.lower().startswith("от"):  # raqam "от" dan oldin keladi
            break
        m = NUMBER.search(token)
        if m and sum(ch.isdigit() for ch in m[0]) >= 2 and not is_date_token(m[0]):
            number = m[0].rstrip(".")
            if number.endswith(("-", "/")):  # bosma boshi, davomi qo'lda — chala raqam olinmaydi
                number = None
            tokens = tokens[k + 1 :]
            break
    return number, parse_date(" ".join(tokens))


def reply_of(first: CachedPage) -> tuple[str | None, str | None] | None:
    """1-sahifadan: avval matn qatlami, unda to'la bo'lmasa — OCR."""
    results = [reply_reference(p) for p in (first.text_layer, first.ocr) if p is not None]
    filled = [r for r in results if r and r[0]]
    if filled:
        return filled[0]
    return next((r for r in results if r is not None), None)


def reply_summary(number: str, date: str) -> str:
    """Xodimlar yozadigan shakl: "05.12.2025-yildagi 17/08-10/2934-son xat ijrosi bo'yicha"."""
    return TEMPLATE.format(date=date, number=number)
