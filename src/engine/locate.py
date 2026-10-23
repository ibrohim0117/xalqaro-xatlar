"""B7.3: qiymat qayerdan olingani — xodimga PDF ustida ko'rsatish uchun.

predict "nima" topilganini aytadi, bu modul — "qayerda". Har maydon uchun to'rtburchaklar:
sahifa raqami va nisbiy koordinatalar (0..1, sahifa o'lchamiga bog'liq emas).
Sana va raqam o'qilmagan bo'lsa ham "№" qatori atrofi ko'rsatiladi: qo'lda yozilgan sana va
raqam aynan shu yerda bo'ladi — xodim o'zi o'qiydi.
"""

from src.fields.boshqarma import evidence_lines, predict_group
from src.fields.date_number import anchor_of
from src.fields.layout import sender_block
from src.fields.reply import reply_anchor_of
from src.fields.signer import find_signer
from src.reading.pages import CachedPage
from src.reading.pdf_text import Word

LINE_PAD = 0.012  # "№" qatori ramkasi yuqori-pastga kengroq: qo'lyozma qatordan chiqib turadi
HANDWRITING_WIDTH = 0.22  # bosma so'z bo'lmasa — "№" dan chapga (sana) va o'ngga (raqam) joy
REPLY_BEFORE = 0.06  # "На" so'zi "№" dan chapda
REPLY_WIDTH = 0.45  # "На № ____ от ____": raqam ham, sana ham "№" dan o'ngda


def _clip(value: float) -> float:
    return round(min(max(value, 0.0), 1.0), 4)


def box(page: int, x0: float, y0: float, x1: float, y1: float) -> dict:
    return {"sahifa": page, "x0": _clip(x0), "y0": _clip(y0), "x1": _clip(x1), "y1": _clip(y1)}


def around(page: int, words: list[Word]) -> dict:
    return box(
        page,
        min(w.x0 for w in words),
        min(w.y0 for w in words),
        max(w.x1 for w in words),
        max(w.y1 for w in words),
    )


def date_number_boxes(first: CachedPage) -> dict[str, list[dict]]:
    """ "<sana> № <raqam>" qatori: "№" dan chapi — sana, o'ngi — raqam."""
    found = anchor_of(first)
    if found is None:
        return {}
    anchor, line = found
    y0, y1 = anchor.y0 - LINE_PAD, anchor.y1 + LINE_PAD
    left = min([w.x0 for w in line if w.x1 <= anchor.x0] + [anchor.x0 - HANDWRITING_WIDTH])
    right = max([w.x1 for w in line if w.x0 > anchor.x0] + [anchor.x0 + HANDWRITING_WIDTH])
    return {
        "hujjat_sana": [box(1, left, y0, anchor.x0, y1)],
        "hujjat_raqami": [box(1, anchor.x0, y0, right, y1)],
    }


def reply_box(first: CachedPage) -> dict | None:
    """ "На № … от …" qatori: javob xatda bizning oldingi xatimiz raqami va sanasi
    (ko'pincha qo'lda yozilgan)."""
    anchor = reply_anchor_of(first)
    if anchor is None:
        return None
    return box(
        1,
        anchor.x0 - REPLY_BEFORE,
        anchor.y0 - LINE_PAD,
        anchor.x0 + REPLY_WIDTH,
        anchor.y1 + LINE_PAD,
    )


HEADER_BOX = {"sahifa": 1, "x0": 0.0, "y0": 0.0, "x1": 0.6, "y1": 0.5}  # dev: "№" y 0.05–0.46


def ocr_regions(first: CachedPage) -> dict[str, dict]:
    """Qo'lyozma OCR uchun bo'laklar (B5.3b): line — "sana № raqam" qatori, date — "№" dan chapi,
    number — o'ngi, reply — "На № … от …", header — chap yuqori qism ("№" topilmasa ham bor)."""
    found = {"header": HEADER_BOX}
    halves = date_number_boxes(first)
    if halves:
        date, number = halves["hujjat_sana"][0], halves["hujjat_raqami"][0]
        found |= {"line": {**date, "x1": number["x1"]}, "date": date, "number": number}
    if (reply := reply_box(first)) is not None:
        found["reply"] = reply
    return found


def locate(pages: list[CachedPage]) -> dict[str, list[dict]]:
    """Maydon -> to'rtburchaklar. Joyi aniqlanmagan maydon ro'yxatga kirmaydi (masalan, mazmun)."""
    first = pages[0]
    boxes: dict[str, list[dict]] = {}
    if blank := sender_block(first):
        boxes["hujjat_junatuvchi_tashkilot"] = [around(1, blank)]
    boxes.update(date_number_boxes(first))
    if signer := find_signer(pages):
        boxes["imzolagan_shaxs"] = [box(signer.page, *signer.box)]
    if lines := evidence_lines(pages, *predict_group(pages)):
        boxes["boshqarma"] = [around(page, words) for page, words in lines]
    return boxes
