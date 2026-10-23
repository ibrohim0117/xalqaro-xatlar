"""B5.2: imzolagan shaxs — xatdagi kirill ismni topish va lotinga o'girish.

json'dagi shakl: bosh harflar va familiya, lotinda: "O.N.Xrushev", "M.Burkadze", "Sh.A.Rahimov".
"""

import re
from dataclasses import dataclass

from src.pdf_text import Word
from src.text_cache import CachedPage

# Rus va o'zbek kirill harflari -> o'zbek lotin yozuvi (rus ismlarini o'zbekcha yozish odati)
CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}  # fmt: skip
VOWELS = set("аеёиоуыэюяў")
# json'dagi imzo: 1–3 ta bosh harf (har biri 1–2 harf va nuqta), keyin familiya
JSON_SIGNER = re.compile(r"^((?:[A-Z][a-z]?\.\s*){1,3})([A-Z][A-Za-z'ʻ’`-]+)$")


def to_latin(word: str) -> str:
    """Kirill so'zni lotinga o'giradi. So'z boshida va unlidan keyin "Е" -> "Ye" (Евгений)."""
    out = []
    for i, ch in enumerate(word):
        low = ch.lower()
        if low == "е" and (i == 0 or word[i - 1].lower() in VOWELS):
            latin = "ye"
        else:
            latin = CYR2LAT.get(low, ch)
        out.append(latin.capitalize() if ch.isupper() and latin else latin)
    return "".join(out)


def parse_json_signer(value: str | None) -> tuple[list[str], str] | None:
    """Masalan "O.N.Xrushev" -> (["O", "N"], "Xrushev"). Shakl boshqacha bo'lsa — None."""
    m = JSON_SIGNER.match((value or "").strip())
    if not m:
        return None
    initials = [part for part in re.split(r"[.\s]+", m.group(1)) if part]
    return initials, m.group(2)


def format_signer(initials: list[str], surname: str) -> str:
    """json shakli: bosh harflar nuqta bilan, bo'shliqsiz, keyin familiya: "O.N.Xrushev"."""
    return "".join(f"{i}." for i in initials) + surname


# ── B5.2b: imzoni xatdan topish ──
# dev: imzo 46 tadan 45 tasida o'ng yarmida, 39 tasida "И.О. Фамилия" shaklida ("Фамилия И.О." — 0).
# Fuqaro ismlari odatda "Иванов П.С." yoki to'liq yoziladi — oldindagi bosh harf imzoni ajratadi.
INITIALS_TOKEN = re.compile(r"(?:[А-ЯЁЎҚҒҲ]\.){1,2}")  # "А.Б." yoki "А." ("А. Б." — ikki so'z)
SURNAME_TOKEN = re.compile(r"[А-ЯЁЎҚҒҲ](?:[а-яёўқғҳ]+|[А-ЯЁЎҚҒҲ]+)(?:-[А-ЯЁ][а-яёА-ЯЁ]+)?")
EDGE = re.compile(r"^[^\wЁё]+|[^\wЁё]+$")
RIGHT_HALF = 0.5
# B5.2b (dev): faqat 1-sahifa (2-sahifa va ilovalarda boshqa odamlar imzosi bor: V1 64%, V4 43%),
# o'ng yarmi va sahifaning pastki yarmi (qabul qiluvchi blokidagi odam ismi imzo bo'lib qolmasin):
# 40 javob, 36 to'g'ri (90%); pastki yarmi filtri olib tashlagan 4 javobning hammasi xato edi
SIGNER_PAGES = 1
SIGNER_MIN_Y = 0.5


@dataclass(frozen=True)
class Candidate:
    page: int
    x0: float
    y0: float
    initials: tuple[str, ...]  # kirill: ("А", "Б")
    surname: str  # kirill: "Сидоров"

    def latin(self) -> str:
        """json shakli: "A.B.Sidorov". Katta harfli "СИДОРОВ" ham shu ko'rinishga keladi."""
        surname = self.surname.capitalize() if self.surname.isupper() else self.surname
        return format_signer([to_latin(i) for i in self.initials], to_latin(surname))


def candidates(pages: list[CachedPage], max_pages: int | None = 2) -> list[Candidate]:
    """ "И.О. Фамилия" shaklidagi barcha joylar: familiyadan oldin 1–2 ta bosh harf so'zi."""
    found = []
    for page in pages[:max_pages]:
        words = page.main.words
        for i, word in enumerate(words):
            surname = EDGE.sub("", word.text)
            if not SURNAME_TOKEN.fullmatch(surname):
                continue
            initials = initials_before(words, i)
            if initials:
                found.append(Candidate(page.number, word.x0, word.y0, tuple(initials), surname))
    return found


def initials_before(words: list[Word], i: int) -> list[str]:
    """Familiyadan oldin, AYNAN SHU QATORDA turgan bosh harflar: "А.Б." yoki "А." "Б." (1–2 ta).
    Qator sharti kerak: aks holda "Иванову П.С." dan keyingi qatordagi "Начальник" ham
    imzo bo'lib qoladi."""
    initials: list[str] = []
    j = i - 1
    while j >= 0 and len(initials) < 2:
        prev = words[j]
        if prev.line != words[i].line or not INITIALS_TOKEN.fullmatch(prev.text.strip(",")):
            break
        initials = re.findall(r"[А-ЯЁЎҚҒҲ]", prev.text) + initials
        j -= 1
    return initials[-2:]


def choose_signer(
    found: list[Candidate], right_only: bool = True, min_y: float = 0.0
) -> Candidate | None:
    """Eng oxirgi sahifadagi eng pastdagi nomzod (o'ng yarmidagilardan, min_y dan pastdagilardan).
    min_y — qabul qiluvchi blokidagi odam nomi ("Заместителю министра А.Б. Иванову") imzo
    bo'lib qolmasligi uchun."""
    pool = [c for c in found if (c.x0 >= RIGHT_HALF or not right_only) and c.y0 >= min_y]
    return max(pool, key=lambda c: (c.page, c.y0), default=None)
