"""B5.3: hujjat sanasi va raqami — blank ostidagi "sana № raqam" qatoridan.

Langar: "№" (yoki "nr."). Raqam — langardan keyin o'sha qatordagi birinchi raqamli so'z;
sana — langar bilan bir balandlikda turgan sana. "На № ___ от ___" (javob qaytarilayotgan xat) va
nusxa oluvchining "на № ... от ..." yozuvi — tuzoq, o'tkazib yuboriladi.

json'dagi shakl: sana "DD.MM.YYYY", raqam xatdagidek ("54/07-16606").
"""

import re

from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText, Word

ANCHOR = re.compile(r"^(?:№|N[°º]|nr\.?)", re.IGNORECASE)  # "№", "№01/301495", "nr.", "N°"
TRAP_BEFORE = re.compile(r"^(?:на|ha|на№)$", re.IGNORECASE)  # "На № ___ от ___" (ha — OCR lotin)
ANCHOR_MAX_Y = 0.5  # langar sahifaning yuqori yarmida (dev: y 0.05–0.46)
SAME_LINE = 0.015  # bir qator: y farqi shundan kichik
DATE_BAND = 0.03  # sana langardan biroz yuqori/pastda bo'lishi mumkin (shtamp)

MONTHS = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6, "июл": 7, "авг": 8,
    "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
    "yan": 1, "fev": 2, "apr": 4, "iyun": 6, "iyul": 7, "avg": 8, "sen": 9, "okt": 10, "noy": 11,
    "dek": 12,
}  # fmt: skip
DMY = re.compile(r"(?<!\d)(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{4}|\d{2})(?!\d)")
YMD = re.compile(r"(?<!\d)(\d{4})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{1,2})(?!\d)")
D_MONTH_Y = re.compile(r"(?<!\d)(\d{1,2})\s*[«»\"']?\s*([а-яёa-z]{3,})\.?\s*(\d{4}|\d{2})(?!\d)")
NUMBER = re.compile(r"[\wА-Яа-яЁё/\-.]*\d[\wА-Яа-яЁё/\-.]*")
CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def plausible_number(value: str) -> bool:
    """Raqam OCR axlati emasmi. Dev: to'g'ri topilgan raqamlar shakli juda har xil (999, 99,
    99-99.99.99.99-99/999), shuning uchun faqat aniq belgi ishlatiladi — ichida kirill harfi
    ("99/9Я", "Я-99999") faqat xatolarda uchradi. Qattiqroq filtr 9 ta to'g'ridan 7 tasini
    o'chirib yuborgan edi."""
    return not CYRILLIC.search(value)


def make_date(day: int, month: int, year: int) -> str | None:
    """Tekshirib, json shakliga keltiradi; sana bo'lmasa (OCR axlati) — None."""
    if year < 100:
        year += 2000
    if not (1 <= day <= 31 and 1 <= month <= 12 and 2000 <= year <= 2030):
        return None
    return f"{day:02d}.{month:02d}.{year}"


def after_ot(low: str, start: int) -> bool:
    """Sana oldida "от" turibdimi: "на № 03/01-48/3702 от 18.11.2025" — boshqa xatning sanasi."""
    return low[max(0, start - 4) : start].strip().endswith("от")


def month_of(word: str) -> int | None:
    return next((n for stem, n in MONTHS.items() if word.startswith(stem)), None)


# Naqsh va undan (kun, oy, yil) qanday olinadi — tartib muhim: avval yil oldinda keladigani
DATE_PATTERNS = [
    (YMD, lambda m: (int(m[3]), int(m[2]), int(m[1]))),  # 2025 / 12 /22
    (DMY, lambda m: (int(m[1]), int(m[2]), int(m[3]))),  # 05.12.2025, 5.12.25
    (D_MONTH_Y, lambda m: (int(m[1]), month_of(m[2]), int(m[3]))),  # 05 ДЕК 2025
]


def parse_date(text: str, skip_after_ot: bool = False) -> str | None:
    """Matndagi birinchi sana: 05.12.2025, 19.12.25, 05 ДЕК 2025, 2025 / 12 /22."""
    low = text.lower()
    for pattern, parts in DATE_PATTERNS:
        for m in pattern.finditer(low):
            if skip_after_ot and after_ot(low, m.start()):
                continue
            day, month, year = parts(m)
            if month and (date := make_date(day, month, year)):
                return date
    return None


def all_dates(text: str) -> list[tuple[str, bool]]:
    """Matndagi BARCHA sanalar, matndagi tartibida: (sana, oldida "от" bormi)."""
    low = text.lower()
    found = []
    for pattern, parts in DATE_PATTERNS:
        for m in pattern.finditer(low):
            day, month, year = parts(m)
            if month and (date := make_date(day, month, year)):
                found.append((m.start(), date, after_ot(low, m.start())))
    return [(date, ot) for _, date, ot in sorted(found)]


def is_date_token(token: str) -> bool:
    """So'z BUTUNLIGICHA sanami: "05.12.2025" — ha. "17/08-10/2934", "3-3-28/16847" — yo'q: ichida
    sanaga o'xshash bo'lak bor ("17/08-10" -> 17.08.2010), lekin raqam guruhlari 3 tadan ko'p."""
    return len(re.findall(r"\d+", token)) == 3 and parse_date(token) is not None


def find_anchor(words: list[Word]) -> int | None:
    """Sana-raqam qatoridagi "№": yuqori yarmida, eng yuqoridagisi, "На №" emas."""
    found = [
        i
        for i, w in enumerate(words)
        if ANCHOR.match(w.text)
        and w.y0 < ANCHOR_MAX_Y
        and not (i > 0 and TRAP_BEFORE.match(words[i - 1].text.strip(".,")))
    ]
    return min(found, key=lambda i: words[i].y0, default=None)


def number_in(tokens: list[str]) -> str | None:
    """So'zlar ichidan birinchi raqam ("№" dan keyingi so'zlar yoki OCR matni). "от" gacha
    qidiriladi: "№ ___ от ___" — raqam yo'q."""
    for token in tokens:
        if token.lower().startswith("от"):
            return None
        m = NUMBER.search(token)
        # is_date_token: "3-3-28/16847" ichidagi "3-3-28" sanaga o'xshasa ham — bu raqam
        if m and sum(ch.isdigit() for ch in m[0]) >= 2 and not is_date_token(m[0]):
            number = m[0].rstrip(".")
            # "52/05-" — bosma boshi, davomi qo'lda yozilgan va o'qilmagan: chala raqam yozilmaydi
            return None if number.endswith(("-", "/")) else number
    return None


def find_number(words: list[Word], anchor: int) -> str | None:
    """Langardan keyin, o'sha qatorda: "№ 54/07-16606" yoki yopishgan "№01/301495"."""
    a = words[anchor]
    rest = ANCHOR.sub("", a.text)  # "№01/301495" -> "01/301495"
    after = sorted(
        (w for w in words if abs(w.y0 - a.y0) <= SAME_LINE and w.x0 > a.x0),
        key=lambda w: w.x0,
    )
    return number_in([rest] + [w.text for w in after])


def parse_number(text: str) -> str | None:
    """OCR o'qigan erkin matndan raqam (B5.3b: kesilgan bo'lak): "30.09.26 № 3-3-28/16847" ->
    "3-3-28/16847". Sana so'zlari o'tkazib yuboriladi, "№" belgisi olib tashlanadi. "№" atrofiga
    bo'shliq qo'yiladi: OCR ba'zan qatorni bo'shliqsiz beradi ("12.03.2026№55/07-1234")."""
    tokens = text.replace("№", " № ").split()
    return number_in([ANCHOR.sub("", token) for token in tokens])


def find_date(words: list[Word], anchor: int) -> str | None:
    """Langar bilan bir balandlikdagi sana (avval o'sha qator, keyin biroz kengroq).
    Oldida "от" turgan sana — boshqa xatniki, olinmaydi."""
    a = words[anchor]
    for band in (SAME_LINE, DATE_BAND):
        line = sorted((w for w in words if abs(w.y0 - a.y0) <= band), key=lambda w: w.x0)
        if date := parse_date(" ".join(w.text for w in line), skip_after_ot=True):
            return date
    return None


def anchor_of(first: CachedPage) -> tuple[Word, list[Word]] | None:
    """ "№" langari va u turgan qator so'zlari (avval matn qatlami, bo'lmasa OCR) — joyni ko'rsatish
    uchun: sana va raqam o'qilmagan bo'lsa ham, qo'lda yozilgani aynan shu qatorda bo'ladi."""
    for page in (first.text_layer, first.ocr):
        if page is not None and (i := find_anchor(page.words)) is not None:
            a = page.words[i]
            return a, [w for w in page.words if abs(w.y0 - a.y0) <= SAME_LINE]
    return None


def date_and_number(page: PageText) -> tuple[str | None, str | None]:
    """1-sahifadan (sana, raqam). Langar topilmasa — (None, None)."""
    anchor = find_anchor(page.words)
    if anchor is None:
        return None, None
    return find_date(page.words, anchor), find_number(page.words, anchor)


def date_number_answer(first: CachedPage) -> tuple[str | None, dict[str, str]]:
    """Yakuniy qoida: (avtomatik yoziladigan sana, takliflar).

    Sana matn qatlamidan topilsa — avtomatik (dev: 13/13); faqat OCR topsa — taklif (dev: 4 tadan
    2 tasi to'g'ri). Raqam — doim faqat taklif: dev'da javob berilganlarning ~yarmi xato, chunki
    ko'p raqam qo'lda yoziladi va matnga tushmaydi. Taklif — xodim tasdiqlaydigan maslahat."""
    tl_date, tl_number = date_and_number(first.text_layer)
    ocr_date, ocr_number = date_and_number(first.ocr) if first.ocr else (None, None)
    suggestions = {}
    if not tl_date and ocr_date:
        suggestions["hujjat_sana"] = ocr_date
    number = tl_number or ocr_number
    if number and plausible_number(number):
        suggestions["hujjat_raqami"] = number
    return tl_date, suggestions
