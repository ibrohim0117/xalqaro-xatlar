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
# "№" dan oldin, shu qatorda shuncha so'z ichida "на" — "На №", "На ваш исх. №", "на исх. №"
# (bizning oldingi xatimiz raqami, jo'natuvchiniki emas). Javob xat (reply) ham shuni ishlatadi
LOOK_BACK = 3
# Bank rekvizitlari: "б/с № 4402…", "р/с №" — "№" dan keyin hisob raqami (10+ raqam) yoki oldida
# rekvizit so'zi bo'lsa, bu sana-raqam qatori emas (yangi xatlar: bitta blankda 3 xat adashgan)
BANK_BEFORE = re.compile(r"^(?:[бркл]/с|а/э|р/сч|сч[её]т|иик|бик|инн|огрн|кпп|окпо|бин|иин)$", re.I)
ACCOUNT = re.compile(r"\d{10,}")
ANCHOR_MAX_Y = 0.5  # langar sahifaning yuqori yarmida (dev: y 0.05–0.46)
SAME_LINE = 0.015  # bir qator: y farqi shundan kichik
DATE_BAND = 0.03  # sana langardan biroz yuqori/pastda bo'lishi mumkin (shtamp)
RECIPIENT_X = 0.45  # o'ng (qabul qiluvchi) bloki shundan o'ngda (layout.RIGHT_BLOCK_X)

MONTHS = {
    "янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6, "июл": 7, "авг": 8,
    "сен": 9, "окт": 10, "ноя": 11, "дек": 12,
    "yan": 1, "fev": 2, "apr": 4, "iyun": 6, "iyul": 7, "avg": 8, "sen": 9, "okt": 10, "noy": 11,
    "dek": 12,
    "jan": 1, "feb": 2, "mar": 3, "may": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10,
    "nov": 11, "dec": 12,  # inglizcha (sertifikatlar: "23.Oct.2025")
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


# OCR bo'laklari matni uchun qo'shimcha shakllar (B5.3c, Ibrohim qo'lda ko'rgan xatlardan). Matn
# qatlamidagi avtomatik sana qoidasiga (13/13) TEGILMAYDI: bo'shliqli shakllar telefon yoki manzilni
# sana deb olishi mumkin — shuning uchun faqat sana kutilgan bo'laklarga (date, line, header, page).
# « 17 » 12 20 25 ý. (Turkmaniston)
TURKMEN = re.compile(r"«\s*(\d{1,2})\s*»[\s._]*(\d{1,2})[\s._]+(20\s?\d{2}|\d{2})(?!\d)")
# 12.11 20 25 г. (yil ikkiga bo'lingan)
SPLIT_YEAR = re.compile(r"(?<!\d)(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]?\s*20\s+(\d{2})(?!\d)")
# 23.Oct.2025 (oy nomi nuqtalar bilan)
D_MON_Y_LOOSE = re.compile(
    r"(?<!\d)(\d{1,2})[\s.\-«»\"']*([а-яёa-z]{3,})[\s.,\-]*(\d{4}|\d{2})(?!\d)"
)
# 19 12.25 (kun va oy orasida bo'shliq)
SPACED = re.compile(r"(?<!\d)(\d{1,2})\s+(\d{1,2})\s*[./-]\s*(\d{4}|\d{2})(?!\d)")
OCR_PATTERNS = DATE_PATTERNS + [
    (TURKMEN, lambda m: (int(m[1]), int(m[2]), int(m[3].replace(" ", "")))),
    (SPLIT_YEAR, lambda m: (int(m[1]), int(m[2]), 2000 + int(m[3]))),
    (D_MON_Y_LOOSE, lambda m: (int(m[1]), month_of(m[2]), int(m[3]))),
    (SPACED, lambda m: (int(m[1]), int(m[2]), int(m[3]))),
]


def inside_number(low: str, start: int, end: int) -> bool:
    """Sanaga o'xshash bo'lak raqamning ichida: "№" ga YOPISHGAN ("№03-01-26"), oldida "raqam/"
    ("78/05-1/25") yoki keyin "/raqam" — "№03-01-26/785" dagi "03-01-26" sana emas (yangi xatlar:
    shunday xato sana chiqqan). Bo'shliq bilan "№ 12.01.2026" — sana bo'lishi mumkin (dev: bitta
    xatda matn qatlami sanani "№" dan keyin bergan; birinchi urinish uni ham to'sib qo'ygan edi)."""
    before, after = low[max(0, start - 2) : start], low[end : end + 2]
    return (
        before[-1:] == "№"
        or (before[-1:] in ("/", "-") and before[:1].isdigit())
        or (after[:1] == "/" and after[1:2].isdigit())
    )


def parse_date(text: str, skip_after_ot: bool = False, patterns=DATE_PATTERNS) -> str | None:
    """Matndagi birinchi sana: 05.12.2025, 19.12.25, 05 ДЕК 2025, 2025 / 12 /22.
    patterns=OCR_PATTERNS — OCR bo'lagi matni uchun (qo'shimcha shakllar bilan)."""
    low = text.lower()
    for pattern, parts in patterns:
        for m in pattern.finditer(low):
            if skip_after_ot and after_ot(low, m.start()):
                continue
            if inside_number(low, m.start(), m.end()):
                continue
            day, month, year = parts(m)
            if month and (date := make_date(day, month, year)):
                return date
    return None


def date_spans(text: str, patterns=DATE_PATTERNS) -> list[tuple[int, int, str, bool]]:
    """Matndagi BARCHA sanalar joyi bilan, tartibda: (boshi, oxiri, sana, oldida "от" bormi)."""
    low = text.lower()
    found = []
    for pattern, parts in patterns:
        for m in pattern.finditer(low):
            if inside_number(low, m.start(), m.end()):
                continue
            day, month, year = parts(m)
            if month and (date := make_date(day, month, year)):
                found.append((m.start(), m.end(), date, after_ot(low, m.start())))
    return sorted(found)


def all_dates(text: str, patterns=DATE_PATTERNS) -> list[tuple[str, bool]]:
    """Matndagi BARCHA sanalar, matndagi tartibida: (sana, oldida "от" bormi)."""
    return [(date, ot) for _, _, date, ot in date_spans(text, patterns)]


def is_date_token(token: str) -> bool:
    """So'z BUTUNLIGICHA sanami: "05.12.2025" — ha. "17/08-10/2934", "3-3-28/16847" — yo'q: ichida
    sanaga o'xshash bo'lak bor ("17/08-10" -> 17.08.2010), lekin raqam guruhlari 3 tadan ko'p."""
    return len(re.findall(r"\d+", token)) == 3 and parse_date(token) is not None


def after_na(words: list[Word], i: int) -> bool:
    """ "№" dan oldin (shu qatorda, LOOK_BACK so'z ichida) "на" bor: "На ваш исх. №"."""
    before = [w for w in words[max(0, i - LOOK_BACK) : i] if w.line == words[i].line]
    return any(TRAP_BEFORE.match(w.text.strip(".,")) for w in before)


def is_account(words: list[Word], i: int) -> bool:
    """ "№" bank rekvizitiga tegishli: oldida "б/с", "ИНН" … yoki keyin 10+ raqamli son."""
    prev = words[i - 1] if i > 0 and words[i - 1].line == words[i].line else None
    if prev is not None and BANK_BEFORE.match(prev.text.strip(".,:")):
        return True
    return bool(ACCOUNT.fullmatch(find_number(words, i) or ""))


def find_anchor(words: list[Word]) -> int | None:
    """Sana-raqam qatoridagi "№": yuqori yarmida, eng yuqoridagisi; "На (ваш исх.) №" va bank
    rekvizitlaridagi "№" emas."""
    found = [
        i
        for i, w in enumerate(words)
        if ANCHOR.match(w.text)
        and w.y0 < ANCHOR_MAX_Y
        and not after_na(words, i)
        and not is_account(words, i)
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
    Oldida "от" turgan sana — boshqa xatniki, olinmaydi. Langar chap blokda bo'lsa — sana ham faqat
    chap blokdan: o'ng blokdagi qabul qiluvchi yozuvi "(№ … от …)" sanasi xatniki emas (yangi
    xatlar: matn qatlami so'zlarni aralash bergan, "от" sanadan oldin turmagan)."""
    a = words[anchor]
    left = a.x0 < RECIPIENT_X
    for band in (SAME_LINE, DATE_BAND):
        line = sorted(
            (w for w in words if abs(w.y0 - a.y0) <= band and (not left or w.x0 < RECIPIENT_X)),
            key=lambda w: w.x0,
        )
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
