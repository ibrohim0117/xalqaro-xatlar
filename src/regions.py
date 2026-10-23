"""B4.1: O'zbekiston hududlari lug'ati va ularni matndan topish.

Xatlar asosan ruscha: bitta hudud ko'p shaklda uchraydi ("Ферганская обл.", "Ферганской области",
"г. Коканд", "Кувасайский р-н") — hammasi bitta kalitga ("fargona") bog'lanadi.
Nomlar ochiq geografik ma'lumot (viloyat, shahar, tuman). Sovet davri nomlari ham qo'shilgan.

Og'irlik: 3 — viloyat darajasi ("... область", "... viloyati"), 2 — shahar yoki tuman,
1 — yolg'iz "Ташкент" (qabul qiluvchi manzilida ham bor, shuning uchun kuchsiz).
"""

import re
from dataclasses import dataclass

from src.evaluate import normalize

STRONG, PLACE, WEAK = 3, 2, 1
DISTRICT = r"\w*\s+(?:р-н|р-на|район\w*|тумани)"  # "Кувасайский р-н", "Бозского района"


def oblast(stem: str) -> tuple[str, int]:
    """Ruscha viloyat: "Ферганская обл.", "Ферганской области"."""
    return rf"\b{stem}\w*\s+(?:обл|област)", STRONG


def viloyat(latin: str, cyrillic: str) -> list[tuple[str, int]]:
    """O'zbekcha viloyat (lotin va kirill): "Farg'ona viloyati", "Фарғона вилояти"."""
    return [(rf"\b{latin}\s+viloyat", STRONG), (rf"\b{cyrillic}\s+вилоят", STRONG)]


def city(stem: str) -> tuple[str, int]:
    """Faqat "г. X" shaklida: nomi odam ismi yoki familiyaga o'xshash shaharlar (Ширин, Каган)."""
    return rf"\bг(?:ор)?\.?\s*{stem}", PLACE


def uz_city(latin: str, cyrillic: str) -> list[tuple[str, int]]:
    """O'zbekcha "Navoiy shahri", "Навоий шаҳар" — yolg'iz nomi ismga o'xshash shaharlar."""
    return [(rf"\b{latin}\s+shaha?r", PLACE), (rf"\b{cyrillic}\s+ша[ҳх]а?р", PLACE)]


def district(stem: str) -> tuple[str, int]:
    """Tuman: "Ферганский район", "Самаркандского р-на" (o'zak + район)."""
    return rf"\b{stem}{DISTRICT}", PLACE


def places(*stems: str) -> list[tuple[str, int]]:
    """Shahar va tumanlar: so'z boshidan qidiriladi (kelishiklar uchun oxiri ochiq)."""
    return [(rf"\b{stem}", PLACE) for stem in stems]


@dataclass(frozen=True)
class Region:
    key: str
    name: str  # o'zbekcha nomi (hisobot uchun)
    json_keys: tuple[str, ...]  # json'dagi boshqarma nomida shu so'z bo'lsa — shu hudud
    patterns: tuple[tuple[str, int], ...]


REGIONS = [
    Region(
        "toshkent_sh",
        "Toshkent shahri",
        ("toshkent shahar", "toshkent shahri"),
        (
            (r"\bг(?:ор)?\.?\s*ташкент\b", STRONG),  # "г. Ташкент", "гор.Ташкент"
            (r"\bгород\w*\s+ташкент", STRONG),
            (r"\btoshkent\s+shaha?r", STRONG),  # "shahar" va "shahri"
            (r"\bтошкент\s+ша[ҳх]а?р", STRONG),
            *places(
                "бектемир",
                "мирабад",
                "мирзо-?\\s?улугбек",
                "сергели",
                "алмазар",
                "учтепин",
                "чиланзар",
                "шайхантах",
                "юнусабад",
                "яккасарай",
                "яшнабад",
                "янгихает",
                "сабир-?\\s?рахимов",
                "собир-?\\s?рахимов",
                "акмал-?\\s?икрамов",
                "хамзинск",
                "yunusobod",
                "юнусобод",
                "chilonzor",
                "чилонзор",
                "mirzo-?\\s?ulug'bek",
                "мирзо-?\\s?улуғбек",
                "yakkasaroy",
                "яккасарой",
                "shayxontohur",
                "шайхонтоҳур",
                "olmazor",
                "олмазор",
                "uchtepa",
                "yashnobod",
                "яшнобод",
                "mirobod",
                "миробод",
                "sergeli",
                "bektemir",
                "yangihayot",
                "янгиҳает",
            ),
            (r"\bташкент(?:а|е|у|ом)?\b", WEAK),  # yolg'iz "Ташкент" — kuchsiz
        ),
    ),
    Region(
        "toshkent_v",
        "Toshkent viloyati",
        ("toshkent viloyat",),
        (
            oblast("ташкентск"),
            (rf"\bташкентск{DISTRICT}", STRONG),  # "Ташкентский район" — viloyatda
            *viloyat("toshkent", "тошкент"),
            (r"\btoshkent\s+tuman", STRONG),  # Toshkent tumani — viloyatda
            (r"\bтошкент\s+туман", STRONG),
            *places("chirchiq", "чирчиқ", "olmaliq", "олмалиқ", "yangiyo'l", "янгийўл"),
            *places("bekobod", "бекобод", "zangiota", "зангиота", "qibray", "қибрай"),
            *places("bo'stonliq", "бўстонлиқ", "ohangaron", "оҳангарон", "chinoz", "чиноз"),
            *places(
                "чирчик",
                "алмалык",
                "ангрен",
                "бекабад",
                "янгиюл",
                "ахангаран",
                "тойтеп",
                "газалкент",
                "паркент",
                "пскент",
                "чиназ",
                "кибрай",
                "зангиат",
                "бостанлык",
                "юкоричирчик",
                "куйичирчик",
                "уртачирчик",
                "верхнечирчик",
                "нижнечирчик",
                "среднечирчик",
                "аккурганск",
                "букинск",
            ),
            city("нурафшан"),
        ),
    ),
    Region(
        "andijon",
        "Andijon viloyati",
        ("andijon",),
        (
            oblast("андижанск"),
            *viloyat("andijon", "андижон"),
            *places("andijon", "андижон"),
            *places(
                "андижан",
                "асака",
                "асакинск",
                "ханабад",
                "шахрихан",
                "ходжаабад",
                "хужаабад",
                "кургантеп",
                "пахтаабад",
                "балыкчи",
                "избаскан",
                "мархаматск",
                "булакбаш",
                "алтынкул",
                "джалакудук",
                "жалакудук",
                "улугнор",
            ),
            (rf"\bбозск{DISTRICT}", PLACE),
        ),
    ),
    Region(
        "buxoro",
        "Buxoro viloyati",
        ("buxoro",),
        (
            oblast("бухарск"),
            *viloyat("buxoro", "бухоро"),
            *places("buxoro", "бухоро"),
            (r"\bбухар[аеуы]\b", PLACE),
            district("бухарск"),
            *places(
                "каганск",
                "гиждуван",
                "вабкент",
                "ромитан",
                "шафиркан",
                "караулбазар",
                "каракульск",
                "жондор",
                "пешку",
                "алатск",
            ),
            city("каган"),
        ),
    ),
    Region(
        "fargona",
        "Farg'ona viloyati",
        ("farg'ona",),
        (
            oblast("ферганск"),
            *viloyat("farg'ona", "фарғона"),
            *places("farg'ona", "фарғона", "qo'qon", "қўқон", "marg'ilon", "марғилон"),
            (r"\bферган[аеуы]\b", PLACE),  # shahar; "Ферганская долина" bu yerga tushmaydi
            district("ферганск"),
            *places(
                "коканд",
                "маргилан",
                "кувасай",
                "кувинск",
                "риштан",
                "бешарык",
                "бешарик",
                "ахунбабаев",
                "алтыарык",
                "олтиарик",
                "язъяван",
                "язяван",
                "фуркатск",
                "ташлакск",
                "учкуприк",
                "бувайд",
                "куштепин",
                "сохск",
            ),
            (rf"\bузбекистанск{DISTRICT}", PLACE),  # Farg'onadagi O'zbekiston tumani
            (rf"\bбагдадск{DISTRICT}", PLACE),
        ),
    ),
    Region(
        "jizzax",
        "Jizzax viloyati",
        ("jizzax",),
        (
            oblast("джизакск"),
            *viloyat("jizzax", "жиззах"),
            *places("jizzax", "жиззах"),
            (r"\bджизак[аеу]?\b", PLACE),
            district("джизакск"),
            *places(
                "зарбдар",
                "галляарал",
                "галлаарал",
                "зафарабад",
                "мирзачул",
                "арнасай",
                "бахмальск",
                "фаришск",
                "шараф-?\\s?рашидов",
            ),
            (rf"\bпахтакорск{DISTRICT}", PLACE),  # yolg'iz "Пахтакор" — futbol klubi ham
        ),
    ),
    Region(
        "xorazm",
        "Xorazm viloyati",
        ("xorazm",),
        (
            oblast("хорезмск"),
            *viloyat("xorazm", "хоразм"),
            *places("urganch", "урганч", "xiva"),
            (r"(?<!куня-)(?<!кене)\bургенч", PLACE),  # Turkmanistondagi Ko'hna Urganch emas
            *places(
                "хива",
                "хивинск",
                "ханкинск",
                "хазарасп",
                "гурлен",
                "шават",
                "янгиарык",
                "кошкупыр",
                "кушкупыр",
                "багатск",
                "питнак",
                "тупроккал",
                "янгибазарск",
            ),
        ),
    ),
    Region(
        "namangan",
        "Namangan viloyati",
        ("namangan",),
        (
            oblast("наманганск"),
            *viloyat("namangan", "наманган"),
            *places("namangan"),
            (r"\bнаманган[аеу]?\b", PLACE),
            district("наманганск"),
            *places(
                "чуст",
                "касансай",
                "чартак",
                "учкурган",
                "уйчи",
                "туракурган",
                "янгикурган",
                "мингбулак",
                "норинск",
            ),
            (rf"\bпапск{DISTRICT}", PLACE),
        ),
    ),
    Region(
        "navoiy",
        "Navoiy viloyati",
        ("navoiy",),
        (
            oblast("навоийск"),
            *viloyat("navoiy", "навоий"),
            *uz_city("navoiy", "навоий"),
            (r"\bг(?:ор)?\.?\s*навои\b", PLACE),  # yolg'iz "Навои" — shoir nomi, ko'chalar
            *places(
                "учкудук",
                "кармана",
                "карманинск",
                "нурата",
                "нуратинск",
                "кызылтеп",
                "хатырчи",
                "навбахор",
                "канимех",
                "тамды",
            ),
            (r"\bг(?:ор)?\.?\s*зарафшан", PLACE),
        ),
    ),
    Region(
        "qashqadaryo",
        "Qashqadaryo viloyati",
        ("qashqadaryo",),
        (
            oblast("кашкадарьинск"),
            *viloyat("qashqadaryo", "қашқадарё"),
            *uz_city("qarshi", "қарши"),
            *places("shahrisabz", "шаҳрисабз"),
            (r"\bкарши\b", PLACE),
            *places("каршинск", "касбийск", "нишанск"),
            *places(
                "шахрисабз",
                "китаб",
                "гузар",
                "мубарек",
                "яккабаг",
                "камаши",
                "чиракчи",
                "дехканабад",
                "миришкор",
                "касанск",
            ),
        ),
    ),
    Region(
        "samarqand",
        "Samarqand viloyati",
        ("samarqand",),
        (
            oblast("самаркандск"),
            *viloyat("samarqand", "самарқанд"),
            *places("samarqand", "самарқанд"),
            (r"\bсамарканд[аеу]?\b", PLACE),
            district("самаркандск"),
            *places(
                "каттакурган",
                "ургут",
                "джамбай",
                "пайарык",
                "акдарь",
                "булунгур",
                "иштыхан",
                "нарпай",
                "пастдарг",
                "тайлакск",
                "кошрабад",
                "нурабад",
            ),
        ),
    ),
    Region(
        "sirdaryo",
        "Sirdaryo viloyati",
        ("sirdaryo",),
        (
            oblast("сырдарьинск"),
            *viloyat("sirdaryo", "сирдарё"),
            *uz_city("guliston", "гулистон"),
            (r"\bг(?:ор)?\.?\s*гулистан|\bгулистанск", PLACE),
            district("сырдарьинск"),
            *places(
                "янгиер",
                "баяут",
                "сайхунабад",
                "хаваст",
                "мирзаабад",
                "акалтын",
                "сардоб",
            ),
            city("ширин"),
        ),
    ),
    Region(
        "surxondaryo",
        "Surxondaryo viloyati",
        ("surxondaryo",),
        (
            oblast("сурхандарьинск"),
            *viloyat("surxondaryo", "сурхондарё"),
            *places("termiz", "термиз"),
            *places(
                "термез",
                "денау",
                "шерабад",
                "джаркурган",
                "кумкурган",
                "байсун",
                "шурчи",
                "музрабад",
                "ангорск",
                "алтынсай",
                "сариасий",
                "кизирик",
                "бандихан",
                "бандихон",
                "узунск",
            ),
        ),
    ),
    Region(
        "qoraqalpog",
        "Qoraqalpog'iston Respublikasi",
        ("qoraqalpog",),
        (
            (r"\bкаракалпак", STRONG),  # Каракалпакстан, Каракалпакская АССР
            (r"\bqoraqalpog", STRONG),
            (r"\bқорақалпоғ", STRONG),
            *places("nukus"),
            *places(
                "нукус",
                "ходжейли",
                "ходжели",
                "берунийск",
                "турткул",
                "кунград",
                "чимбай",
                "тахиаташ",
                "муйнак",
                "элликкал",
                "амударьинск",
                "кегейли",
                "шуманай",
                "канлыкул",
                "тахтакупыр",
                "караузяк",
                "бозатау",
            ),
            city("беруни"),
        ),
    ),
]

# Ko'cha yoki "nomidagi" bo'lsa — hudud emas: "ул. Алишера Навои", "Ферганская улица" emas,
# balki "ул. Ферганская", "им. Навои". Hudud nomidan oldingi 0–2 so'zga qaraladi.
NOT_A_PLACE_BEFORE = re.compile(
    r"(?:\bул|\bулиц\w*|\bпр-т|\bпросп\w*|\bпер|\bпереул\w*|\bпроезд\w*|\bбульв\w*|\bшоссе"
    r"|\bим|\bимени)\.?\s*(?:[\w-]+\.?\s+){0,2}$"
)
COMPILED = [(r.key, re.compile(p), w) for r in REGIONS for p, w in r.patterns]


@dataclass(frozen=True)
class Hit:
    key: str  # hudud kaliti
    weight: int
    start: int  # tayyorlangan matndagi joyi
    end: int
    text: str  # topilgan bo'lak (tekshirish uchun)


def prepare(text: str) -> str:
    """Kichik harf, apostrof/chiziq/bo'shliqlar bir xil, ё -> е."""
    return normalize(text).replace("ё", "е")


def find_regions(text: str) -> list[Hit]:
    """Matndagi barcha hudud eslatmalari, matndagi tartibida."""
    low = prepare(text)
    hits = []
    for key, pattern, weight in COMPILED:
        for m in pattern.finditer(low):
            if NOT_A_PLACE_BEFORE.search(low[max(0, m.start() - 30) : m.start()]):
                continue
            hits.append(Hit(key, weight, m.start(), m.end(), m.group()))
    # Bir joyni qoplagan topilmalardan faqat eng kuchlisi qoladi:
    # "г. Ташкент" — kuchli (3), ichidagi "Ташкент" (1) qayta sanalmaydi
    kept: list[Hit] = []
    for hit in sorted(hits, key=lambda h: -h.weight):
        if all(hit.end <= k.start or hit.start >= k.end for k in kept):
            kept.append(hit)
    return sorted(kept, key=lambda h: h.start)


def region_of_boshqarma(name: str | None) -> str | None:
    """json'dagi boshqarma nomidan hudud kaliti ("Farg'ona viloyati adliya ..." -> "fargona")."""
    low = prepare(name or "")
    for region in REGIONS:
        if any(k in low for k in region.json_keys):
            return region.key
    return None
