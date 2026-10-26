"""B5.4: javob xat — "На № <raqam> от <sana>" qatori: xat BIZNING oldingi xatimizga javob.

Bunday xatlarning qisqacha mazmuni xodimlar yozgan json'da "<sana>-yildagi <raqam>-son xat ijrosi
bo'yicha" shaklida (Ibrohim ko'rgan dev xat); boshqarmani raqam boshidagi indeksdan bilish mumkin
(Ulug'bek: 15 ta javob xatda 15/15). date_number "На №" ni tuzoq deb o'tkazib yuboradi — bu modul
aynan o'sha qatorni o'qiydi.

Langar: "№", undan oldin o'sha qatorda (3 so'z ichida) "на" — "На №", "На Ваш №", "на исх. №".

B5.6: sarlavhadagi "На №" qatori odatda qo'lda to'ldiriladi (dev: qolipdagi 11 xatdan 8 tasida bo'sh
yoki o'qilmagan). Lekin bizning raqamimiz 10/11 xatda 1-sahifada BOSMA bor — oldida "Ваш запрос"
emas, "Министерства юстиции Республики Узбекистан" (explain_reply). Bizning raqamlarimiz o'ziga xos
shaklda (11/11 tuzilishi 9/9-9/9) — our_reference shu shakl bo'yicha qidiradi, xatning o'z raqamini
o'tkazadi, yonidagi sanani oladi (dev, LOO: 9/11 aniq, oddiy xatlarda zarar 0; birinchi urinish —
"Ваш запрос" + birinchi "№" — 6 topgan, 0 mos edi: bizning raqamimizdan oldin boshqa "№" lar bor).
"""

import re

from src.common.text import normalize
from src.fields.date_number import (
    ANCHOR,
    ANCHOR_MAX_Y,
    NUMBER,
    SAME_LINE,
    after_na,
    date_and_number,
    date_spans,
    is_date_token,
    parse_date,
)
from src.fields.number_template import key, shape
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText, Word

OUR_NEAR = 12  # so'z: bizning raqamimiz yonidagi sana shuncha so'z ichida (dev: 9/10)
OT_BONUS = 20  # belgi: "от" dan keyingi sana shuncha belgi uzoqroq bo'lsa ham afzal
JOINED = re.compile(r"^на№", re.IGNORECASE)  # "На№17/08-10/2934" — bo'shliqsiz yozilgan
TEMPLATE = "{date}-yildagi {number}-son xat ijrosi bo'yicha"
SUMMARY = re.compile(  # json'dagi javob mazmuni (normalize qilingan)
    r"^(\d{1,2}\.\d{1,2}\.\d{4})\s*-?\s*y(?:il)?dagi\s+(.+?)\s*-?\s*son\s+xat\s+ijrosi\s+bo'yicha$"
)


def is_reply_anchor(words: list[Word], i: int) -> bool:
    word = words[i]
    if word.y0 >= ANCHOR_MAX_Y:
        return False
    if JOINED.match(word.text):
        return True
    return bool(ANCHOR.match(word.text)) and after_na(words, i)


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


def parse_reply_summary(summary: str | None) -> tuple[str, str] | None:
    """json'dagi javob mazmunidan (sana, raqam); qolipda bo'lmasa — None."""
    found = SUMMARY.match(normalize(summary)) if summary else None
    return (found[1], found[2]) if found else None


def own_numbers(first: CachedPage) -> set[str]:
    """Xatning O'Z raqami ("sana № raqam" qatori; matn qatlami va OCR) — key ko'rinishida."""
    pages = [p for p in (first.text_layer, first.ocr) if p is not None]
    return {key(number) for page in pages if (number := date_and_number(page)[1])}


def candidate_at(tokens: list[str], i: int) -> str | None:
    """tokens[i] dagi raqam ("№17/08-10/2934," -> "17/08-10/2934"); ikki so'zga bo'lingan bo'lsa
    ("17/08-10/" "2934") — qo'shiladi."""
    found = NUMBER.search(tokens[i].split("№")[-1])
    if not found:
        return None
    number = found[0].rstrip(".,")
    tail = NUMBER.match(tokens[i + 1]) if i + 1 < len(tokens) else None
    if number.endswith(("/", "-")) and tail:
        number += tail[0].rstrip(".,")
    return number


def our_reference(
    pages: list[CachedPage], own: set[str], shapes: set[str]
) -> tuple[str, str] | None:
    """(raqam, sana) — bizning oldingi xatimiz: shakli shapes'da (boshqa javob xatlardan
    o'rganilgan), xatning o'z raqami (own — key ko'rinishida) emas, yonida (OUR_NEAR so'z) sana —
    "от" dan keyingisi afzal. Sahifalar tartibida, birinchi topilgani."""
    for page in pages:
        tokens = page.main.text.split()
        for i in range(len(tokens)):
            number = candidate_at(tokens, i)
            if not number or shape(number) not in shapes or key(number) in own:
                continue
            if date := nearest_date(tokens, i, number):
                return number, date
    return None


def nearest_date(tokens: list[str], i: int, number: str) -> str | None:
    """tokens[i] dagi raqamga eng yaqin sana (OUR_NEAR so'z ichida), "от" dan keyingisi afzal.
    Raqamning o'z ichidagi "sana" ("17/08-10/2934" -> 17.08.2010) olinmaydi."""
    before = " ".join(tokens[max(0, i - OUR_NEAR) : i])
    start = len(before) + 1 if before else 0  # raqam matnda shu joydan boshlanadi
    text = " ".join([*filter(None, [before]), *tokens[i : i + OUR_NEAR + 1]])
    split = key(number) not in key(tokens[i])  # davomi keyingi so'zda: "17/08-10/" "2934"
    end = start + len(tokens[i]) + (len(tokens[i + 1]) + 1 if split else 0)
    best = None
    for first, last, date, after_ot in date_spans(text):
        if first < end and last > start:  # raqamning ichida
            continue
        distance = start - last if last <= start else first - end
        score = distance - (OT_BONUS if after_ot else 0)
        if best is None or score < best[0]:
            best = (score, date)
    return best[1] if best else None
