"""B5.2: imzolagan shaxs — xatdagi kirill ismni topish va lotinga o'girish.

json'dagi shakl: bosh harflar va familiya, lotinda: "O.N.Xrushev", "M.Burkadze", "Sh.A.Rahimov".
"""

import re
from dataclasses import dataclass, field

from src.common.text import to_latin
from src.reading.pages import CachedPage
from src.reading.pdf_text import Word

# json'dagi imzo: 1–3 ta bosh harf (har biri 1–2 harf va nuqta), keyin familiya
JSON_SIGNER = re.compile(r"^((?:[A-Z][a-z]?\.\s*){1,3})([A-Z][A-Za-z'ʻ’`-]+)$")


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
UPPER, LOWER = "А-ЯЁЎҚҒҲІЇЄҐ", "а-яёўқғҳіїєґ"  # rus, o'zbek va ukrain kirill harflari
# "А.Б." yoki "А." ("А. Б." — ikki so'z). B5.9 (dev): PDF matni "А.Б." ni "А" va ".Б." ga bo'lgan
# (2 xat) va oxirgi nuqta o'rnida vergul "А.Б," (1 xat) — ".Б." va "А.Б" ham bosh harf
INITIALS_TOKEN = re.compile(rf"\.?(?:[{UPPER}]\.){{1,2}}|[{UPPER}]\.[{UPPER}]")
BARE_INITIAL = re.compile(rf"[{UPPER}]")  # faqat ".Б." oldida: "А" ".Б." (yolg'iz "В" — so'z)
SURNAME_TOKEN = re.compile(rf"[{UPPER}](?:[{LOWER}]+|[{UPPER}]+)(?:-[{UPPER}][{LOWER}{UPPER}]+)?")
# B5.9 (dev 4 xat): bosh harf familiyaga yopishgan — "А.Сидоров", "А.Б.Сидоров"
GLUED = re.compile(rf"((?:[{UPPER}]\.){{1,2}})({SURNAME_TOKEN.pattern})")
# B5.9: Ukraina imzosi "Олена МЕЛЬНИЧУК" — ism va KATTA familiya; json'da 1 bosh harf (dev 4/4)
GIVEN_NAME = re.compile(rf"[{UPPER}][{LOWER}]{{2,}}")
TITLE = re.compile(r"начальник|заместител|директор|руководител|министр|председател|консул|глава")
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
    # bosh harflar + familiya egallagan joy (x0, y0, x1, y1) — xodimga ko'rsatish uchun
    box: tuple[float, float, float, float] = field(default=(0.0, 0.0, 0.0, 0.0), compare=False)
    # B5.9: bosh harflar ".Б." yoki ",Б." bilan boshlanadi, oldidagi harf matnda yo'q — birinchi
    # bosh harf PDF matnida yo'qolgan (dev 3/3 xato edi) -> yoziladi, lekin "tekshiring"
    damaged: bool = field(default=False, compare=False)

    def latin(self) -> str:
        """json shakli: "A.B.Sidorov". Katta harfli "СИДОРОВ" ham shu ko'rinishga keladi."""
        surname = self.surname.capitalize() if self.surname.isupper() else self.surname
        return format_signer([initial_latin(i) for i in self.initials], to_latin(surname))


def initial_latin(letter: str) -> str:
    """Bosh harf lotinda. B5.9: "Е." xodimlar "E." deb yozadi (so'z boshidagi "Ye" emas; dev: 3 xato
    shundan edi)."""
    latin = to_latin(letter)
    return "E" if latin == "Ye" else latin


def candidates(pages: list[CachedPage], max_pages: int | None = 2) -> list[Candidate]:
    """ "И.О. Фамилия" shaklidagi barcha joylar: familiyadan oldin 1–2 ta bosh harf so'zi."""
    found = []
    for page in pages[:max_pages]:
        words = page.main.words
        for i, word in enumerate(words):
            surname = EDGE.sub("", word.text)
            if glued := GLUED.fullmatch(surname):
                initials, start = re.findall(rf"[{UPPER}]", glued.group(1)), i
                surname = glued.group(2)
            elif not SURNAME_TOKEN.fullmatch(surname):
                continue
            else:
                initials, start = initials_before(words, i)
                if not initials:
                    initials, start = given_name_before(words, i)
            if initials:
                used = words[start : i + 1]
                box = (
                    min(w.x0 for w in used),
                    min(w.y0 for w in used),
                    max(w.x1 for w in used),
                    max(w.y1 for w in used),
                )
                damaged = words[start].text[:1] in ".,"
                found.append(
                    Candidate(page.number, word.x0, word.y0, tuple(initials), surname, box, damaged)
                )
    return found


def given_name_before(words: list[Word], i: int) -> tuple[list[str], int]:
    """ "Олена МЕЛЬНИЧУК": familiya KATTA harfda, oldida (shu qatorda) ism — bosh harfi ismdan.
    Lavozim so'zi ("Начальник ОТДЕЛА") ism emas. Familiya qatordagi oxirgi so'z bo'lishi kerak:
    dev'da imzo 4/4 shunday, gap ichidagi "Республики УЗБЕКИСТАН ..." esa imzo bo'lib qolgan edi."""
    surname = EDGE.sub("", words[i].text)
    last_on_line = i + 1 == len(words) or words[i + 1].line != words[i].line
    if i == 0 or not surname.isupper() or not last_on_line:
        return [], i
    prev = words[i - 1]
    name = EDGE.sub("", prev.text)
    if prev.line != words[i].line or not GIVEN_NAME.fullmatch(name) or TITLE.search(name.lower()):
        return [], i
    return [name[0]], i - 1


def initials_before(words: list[Word], i: int) -> tuple[list[str], int]:
    """Familiyadan oldin, AYNAN SHU QATORDA turgan bosh harflar: "А.Б." yoki "А." "Б." (1–2 ta)
    va birinchi bosh harf so'zining o'rni.
    Qator sharti kerak: aks holda "Иванову П.С." dan keyingi qatordagi "Начальник" ham
    imzo bo'lib qoladi."""
    initials: list[str] = []
    j = i - 1
    while j >= 0 and len(initials) < 2:
        prev = words[j]
        if prev.line != words[i].line or not INITIALS_TOKEN.fullmatch(prev.text.strip(",")):
            break
        initials = re.findall(rf"[{UPPER}]", prev.text) + initials  # "І.В." ham
        j -= 1
    # "А" ".Б." — bo'lingan "А.Б.": ".Б." oldidagi yolg'iz katta harf ham bosh harf
    first = words[j + 1]
    split = initials and first.text.startswith(".") and j >= 0 and words[j].line == first.line
    if split and BARE_INITIAL.fullmatch(words[j].text):
        initials = [words[j].text] + initials
        j -= 1
    return initials[-2:], j + 1


def choose_signer(
    found: list[Candidate], right_only: bool = True, min_y: float = 0.0
) -> Candidate | None:
    """Eng oxirgi sahifadagi eng pastdagi nomzod (o'ng yarmidagilardan, min_y dan pastdagilardan).
    min_y — qabul qiluvchi blokidagi odam nomi ("Заместителю министра А.Б. Иванову") imzo
    bo'lib qolmasligi uchun."""
    pool = [c for c in found if (c.x0 >= RIGHT_HALF or not right_only) and c.y0 >= min_y]
    return max(pool, key=lambda c: (c.page, c.y0), default=None)


def find_signer(pages: list[CachedPage]) -> Candidate | None:
    """Imzo: 1-sahifa, o'ng yarmi, pastki yarmi (B5.2b qoidasi). predict ham, joyni ko'rsatish ham
    shu bitta funksiyani ishlatadi — qoida bir joyda."""
    return choose_signer(candidates(pages, SIGNER_PAGES), min_y=SIGNER_MIN_Y)
