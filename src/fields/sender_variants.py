"""B5.1c-3: notanish jo'natuvchi uchun o'zbekcha nom variantlari (lug'at + qoliplar).

Blankdan uch bo'lak ajratiladi: davlat, hudud va tashkilot turi; ular qolipga qo'yiladi.
Qoliplar dev'dagi 27 ta jo'natuvchi nomidan olingan (xodimlar qanday yozgani):
"Rossiya Federatsiyasi Adliya vazirligining Nijegorodsk viloyati bo'yicha bosh boshqarmasi",
"Rostov viloyati FHDY bo'limi", "Turkmaniston Adliya vazirligi",
"RF IIV Tver viloyati bo'yicha boshqarmasi".
Variantlar xodimga taklif qilinadi — u tanlaydi yoki tuzatadi, tanlangani xotiraga yoziladi.
"""

import re

from src.common.text import to_latin
from src.fields.layout import RIGHT_BLOCK_X, header_bottom
from src.fields.regions import find_regions, prepare
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText

VARIANT_MIN_Y = (
    0.35  # blank kamida sahifaning yuqori 35% i: tepadagi boshqa "№" (shtamp) kesib qo'ymasin
)

# ── 1. Davlat: ruscha shakli -> xodimlar yozadigan o'zbekcha nom ──
COUNTRIES = [  # (naqsh, nom) — "Узбекистан" ataylab yo'q: u qabul qiluvchi
    (r"российской\s+федерации|\bрф\b|\bроссии\b|минюст[а-я]*\s+россии", "Rossiya Federatsiyasi"),
    (r"туркменистан|t[uü]rkmenistan", "Turkmaniston"),
    (r"украин", "Ukraina"),
    (r"беларус", "Belarus Respublikasi"),
    (r"грузи", "Gruziya"),
    (r"китайской\s+народной|\bкнр\b|\bchina\b|中华人民共和国|中国", "Xitoy Xalq Respublikasi"),
    (r"молдов|moldova", "Moldova Respublikasi"),
    (r"казахстан", "Qozog'iston Respublikasi"),
    (r"кыргыз|киргиз", "Qirg'iziston Respublikasi"),
    (r"таджикистан", "Tojikiston Respublikasi"),
    (r"азербайджан", "Ozarbayjon Respublikasi"),
    (r"армени", "Armaniston Respublikasi"),
    (r"аргентин|argentin", "Argentina Respublikasi"),
]

# ── 2. Hudud: "по Нижегородской области", "Ставропольского края", "Республики Бурятия" ──
# "-скои": skaner OCR "Й" ni ko'pincha "И" deb o'qiydi ("НОВОСИБИРСКОИ ОБЛАСТИ")
REGION = re.compile(
    r"([а-яё-]{4,}(?:ской|скои|ского|ская|ий|ой|ои))\s+(област\w*|обл\b|кра[яюй]\w*)"
)
# "Республика Калмыкия", "Республики Коми" — ot shaklidagi "республика" ("республиканское" emas)
REPUBLIC = re.compile(r"\bреспублик(?:а|и|е|у|ой)\s+([а-яё-]{3,})")
NOT_REGION = {"узбекистан"}  # qabul qiluvchi davlat — jo'natuvchining hududi emas
REGION_TYPE = {"обл": "viloyati", "кра": "o'lkasi"}
# Sifatdan yasab bo'lmaydigan nomlar (xodimlar yozgani)
IRREGULAR = {
    "московск": "Moskva",
    "пензенск": "Penza",
    "ивановск": "Ivanovo",
    "жамбылск": "Jambil",
    "башкортостан": "Boshqirdiston",
    "татарстан": "Tatariston",
    "бурятия": "Buryatiya",
    "дагестан": "Dog'iston",
}


def find_country(low: str) -> str | None:
    for pattern, name in COUNTRIES:
        if re.search(pattern, low):
            return name
    return None


def region_names(adjective: str) -> list[str]:
    """Ruscha sifatdan joy nomi shakllari: "нижегородской" -> ["Nijegorod", "Nijegorodsk"].
    Xodimlar ikkalasini ham ishlatgan: Rostov, Saratov, Tver; Nijegorodsk, Novosibirsk (+sk)."""
    base = re.sub(r"(ой|ои|ого|ая|ий|ом)$", "", adjective)  # "нижегородск"
    if base in IRREGULAR:
        return [IRREGULAR[base]]
    names = [to_latin(base).capitalize()]  # "Nijegorodsk"
    if base.endswith("ск"):
        names.insert(0, to_latin(base[:-2]).capitalize())  # "Nijegorod"
    return names


def find_region(low: str) -> tuple[list[str], str] | None:
    """(joy nomi shakllari, turi): (["Nijegorod", "Nijegorodsk"], "viloyati")."""
    for m in REGION.finditer(low):
        if find_regions(m[0]):  # O'zbekiston hududi ("Кашкадарьинской области") — jo'natuvchi emas
            continue
        return region_names(m[1]), REGION_TYPE.get(m[2][:3], "viloyati")
    for m in REPUBLIC.finditer(low):
        name = m[1]
        if name in IRREGULAR:  # Rossiya ichidagi respublikalar: xodimlar yozadigan o'zbekcha nom
            return [IRREGULAR[name]], "Respublikasi"
        # yangi xatlar: ro'yxat dev'dagi 4 respublika bilan cheklangan edi — "Калмыкия" ko'rinmagan.
        # Endi istalgan respublika nomi lotinga o'giriladi ("Kalmikiya"); davlat nomlari — alohida
        if name not in NOT_REGION and not find_country(name):
            return [to_latin(name).capitalize()], "Respublikasi"
    return None


# ── 3. Tashkilot turi va qoliplar ──
# Qabul qiluvchi ("… при Министерстве юстиции Республики Узбекистан") — olib tashlanadi
RECIPIENT = re.compile(
    r"(?:агентств\w*\s+государственных\s+услуг\s+)?(?:при\s+)?"
    r"министерств\w*\s+юстиции\s+республики\s+узбекистан\w*"
)
JUSTICE_GU = re.compile(r"управлени\w*\s+(?:министерства\s+юстиции|минюста)")
ZAGS = re.compile(r"загс|записи\s+актов\s+гражданского")
MVD = re.compile(r"\bу?мвд\b|внутренних\s+дел")
JUSTICE_DEPT = re.compile(r"департамент\w*\s+юстиции")
AGENCY = re.compile(
    r"агентств\w*\s+(?:по\s+развитию\s+)?(?:государственных|публичных)\s+(?:услуг|сервисов)"
    r"|agen\w*\s+servicii"
)
MINISTRY = re.compile(
    r"министерств\w*\s+юстиции|ministry\s+of\s+justice|ministerio\s+de\s+justicia"
    r"|ministerul\s+justi|adalat\s+ministrlig|司法部"
)
GOV_FOR_CITIZENS = re.compile(r"правительство\s+для\s+граждан.{0,40}?по\s+городу\s+([а-яё-]+)")
MOSCOW_CITY = re.compile(r"по\s+(?:городу\s+|г\.\s*)?москв")
# ZAGS bo'linmasi: ruscha so'z -> xodimlar yozgani (отдел -> bo'limi, комитет -> qo'mitasi …)
ZAGS_UNITS = [
    (r"территориальн\w*\s+отдел", "hududiy bo'limi"),
    (r"управлени", "boshqarmasi"),
    (r"комитет", "qo'mitasi"),
    (r"служб", "xizmati"),
    (r"отдел|орган", "bo'limi"),
]


def zags_unit(low: str) -> str:
    """ZAGS qanday bo'linma: "ЗАГС" dan oldingi ENG YAQIN so'z ("Государственный комитет ...
    отдел ЗАГС" -> "bo'limi"). Topilmasa — eng ko'p uchragani ("bo'limi")."""
    m = ZAGS.search(low)
    window = low[max(0, m.start() - 60) : m.start()] if m else low
    best, position = "bo'limi", -1
    for ru, uz in ZAGS_UNITS:
        for found in re.finditer(ru, window):
            if found.start() > position:
                best, position = uz, found.start()
    if re.search(r"территориальн\w*\s+отдел\s*$", window.strip() + " "):
        best = "hududiy bo'limi"
    return best


def sender_variants(blank: str, limit: int = 4) -> list[str]:
    """Blankdan o'zbekcha nom variantlari, eng ehtimollisi birinchi. Topilmasa — bo'sh ro'yxat."""
    low = RECIPIENT.sub(" ", prepare(blank))
    country = find_country(low)
    region = find_region(low)
    out: list[str] = []
    if region:
        names, kind = region
        if JUSTICE_GU.search(low):  # Rossiya Adliya vazirligi viloyat bosh boshqarmasi
            c = country or "Rossiya Federatsiyasi"
            out += [f"{c} Adliya vazirligining {n} {kind} bo'yicha bosh boshqarmasi" for n in names]
            out.append(f"{c} Adliya vazirligi {names[-1]} {kind} Bosh boshqarmasi")
            out.append(f"{c} {names[0]} {kind} bo'yicha bosh boshqarmasi")  # "Primor o'lkasi" kabi
        if ZAGS.search(low):  # FHDY (ZAGS) bo'limi
            # Dev: xodimlar ko'pincha "bo'limi" yozgan (7 marta), ruschada "управление" bo'lsa ham
            units = list(dict.fromkeys(["bo'limi", zags_unit(low)]))
            if "правительств" in low:
                out.append(f"{names[0]} {kind} Hukumati FHDY {units[0]}")
            out += [f"{n} {kind} FHDY {u}" for u in units for n in names]
        if MVD.search(low):  # ichki ishlar
            prefix = "RF IIV" if country in (None, "Rossiya Federatsiyasi") else f"{country} IIV"
            out += [f"{prefix} {n} {kind} bo'yicha boshqarmasi" for n in names]
        if JUSTICE_DEPT.search(low) and country:  # Qozog'iston adliya departamenti
            out += [f"{country} Adliya vazirligi {n} {kind} adliya departamenti" for n in names]
    if MOSCOW_CITY.search(low) and JUSTICE_GU.search(low):
        out += ["RF Adliya vazirligi Moskva bo'yicha bosh boshqarmasi"]
    if m := GOV_FOR_CITIZENS.search(low):  # Qozog'iston "Правительство для граждан"
        out.append(f'GK "Pravitelstvo dlya grajdan" po gorodu {to_latin(m[1]).capitalize()}')
    if country and AGENCY.search(low):  # Gruziya agentligi xati vazirlik nomi bilan yozilgan
        out += [f"{country} Adliya vazirligi", f"{country} Davlat xizmatlari agentligi"]
    if country and (MINISTRY.search(low) or not out):
        out.append(f"{country} Adliya vazirligi")
    return list(dict.fromkeys(out))[:limit]  # takrorlarsiz, tartib saqlanadi


GENERIC = re.compile(r"[\w' ]+ Adliya vazirligi")  # faqat "X Adliya vazirligi" — eng umumiy variant


def variants_texts(pages: list[CachedPage]) -> list[str]:
    """Blank matni ikki tartibda: (1) chap ustun, keyin o'ng ustun — OCR ikki blokni bitta qatorga
    qo'shganda ("ГЛАВНОЕ УПРАВЛЕНИЕ Республики Узбекистан") iborani tiklaydi; (2) oddiy qatorlar —
    markazdagi blankda ("Республики Башкортостан") ibora ustunlarga bo'linib ketmasligi uchun."""
    first = pages[0]
    main = first.main
    bottom = max(header_bottom(first), VARIANT_MIN_Y)
    words = [w for w in main.words if w.y0 < bottom]
    left = [w for w in words if w.x0 < RIGHT_BLOCK_X]
    right = [w for w in words if w.x0 >= RIGHT_BLOCK_X]
    by_columns = PageText(1, main.source, left).text + "\n" + PageText(1, main.source, right).text
    return [by_columns, PageText(1, main.source, words).text]


def page_variants(pages: list[CachedPage], limit: int = 4) -> list[str]:
    """Ikkala tartib variantlari birlashadi: aniqroqlari oldinda, "X Adliya vazirligi" — oxirida."""
    merged = list(dict.fromkeys(v for text in variants_texts(pages) for v in sender_variants(text)))
    specific = [v for v in merged if not GENERIC.fullmatch(v)]
    return (specific + [v for v in merged if GENERIC.fullmatch(v)])[:limit]


def blank_places(pages: list[CachedPage]) -> list[str]:
    """B5.8: blankdagi joy — hudud nomi shakllari ("Nijegorod", "Nijegorodsk"), hudud bo'lmasa
    davlat ("Moldova"). Tanilgan tashkilot nomida shu joy bormi — margin qoidasi uchun himoya:
    notanish tashkilot tuzilishi o'xshash boshqasi bilan adashmasin (Moldova ≠ Gruziya)."""
    places: list[str] = []
    for text in variants_texts(pages):
        low = RECIPIENT.sub(" ", prepare(text))
        if region := find_region(low):
            places += region[0]
        elif country := find_country(low):
            places.append(country.split()[0])
    return list(dict.fromkeys(places))


def same_place(places: list[str], name: str) -> bool:
    """Tashkilot nomida blankdagi joylardan biri bormi (joy topilmagan bo'lsa — yo'q, ehtiyot)."""
    low = prepare(name)
    russia = "Rossiya" in places and re.match(r"rf\b", low)
    return bool(russia) or any(prepare(place) in low for place in places)
