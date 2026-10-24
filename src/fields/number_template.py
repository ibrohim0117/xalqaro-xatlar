"""B5.5-3: tashkilot raqam qolipi — VLM o'qigan raqamni tekshirish va tuzatish.

Bitta tashkilot xatlarining raqami odatda bir xil TUZILISHDA (ajratgichlar tartibi bir xil:
9/9-9/9 — har "9" bir guruh raqam, uzunligi har xil bo'lishi mumkin) va bir xil BOSH QISM bilan
boshlanadi (viloyat va bo'lim kodi: "54/07-"); qo'lda faqat tartib raqami yoziladi. Qolip shu
tashkilotning BOSHQA xatlaridan o'rganiladi (fit_numbers o'lchovida — xatni o'zidan o'rgatmaslik
uchun). Sanadagi "kun ≤ 31, oy ≤ 12" tekshiruvining raqamdagi o'rni.
"""

import re
from collections import Counter
from dataclasses import dataclass

from src.common.text import normalize

SEPARATORS = "/-._\\"
PART = re.compile(r"[/\-._\\]|[^/\-._\\]+")  # bo'laklar: "54", "/", "07", "-", …


def key(number: str | None) -> str:
    """Solishtirish uchun: bo'shliqsiz, kichik harf (evaluate.compare bilan bir xil)."""
    return normalize(number, spaceless=True)


def structure(number: str) -> str:
    """Raqam tuzilishi: raqamlar guruhi -> 9, harfli guruh -> A, ajratgich o'zi
    ("54/07-16606/25" -> "9/9-9/9")."""
    return "".join(
        part if part in SEPARATORS else "9" if part.isdigit() else "A"
        for part in PART.findall(key(number))
    )


def shape(number: str) -> str:
    """To'liq shakl — har raqam 9, harf A ("17/08-10/2934" -> "99/99-99/9999"): tuzilishdan
    aniqroq (guruh uzunligi ham), qiymatni esa ko'rsatmaydi."""
    return "".join("9" if c.isdigit() else c if c in SEPARATORS else "A" for c in key(number))


def skeleton(shape: str) -> str:
    """Tuzilish, ajratgich turisiz ("9/9-9/9" -> "9|9|9|9")."""
    return re.sub(r"[/\-._\\]", "|", shape)


def bare(value: str) -> str:
    """Ajratgichlarsiz ("54/07-" -> "5407")."""
    return "".join(c for c in value if c not in SEPARATORS)


@dataclass(frozen=True)
class Template:
    structure: str  # "9/9-9/9"
    prefix: str  # doimiy bosh qism ("54/07-"); bo'lmasa — ""


def learn(numbers: list[str], min_letters: int = 2) -> Template | None:
    """Tashkilotning boshqa xatlari raqamlaridan qolip: yarmidan ko'pi bir tuzilishda bo'lsa — shu
    tuzilish, va o'sha tuzilishdagi hamma raqamlarda bir xil bo'lgan boshidagi bo'laklar."""
    keys = [key(n) for n in numbers if n and key(n)]
    if len(keys) < min_letters:
        return None
    common, count = Counter(structure(k) for k in keys).most_common(1)[0]
    if count * 2 <= len(keys):
        return None
    same = [PART.findall(k) for k in keys if structure(k) == common]
    prefix = []
    for column in zip(*same, strict=True):
        if len(set(column)) > 1:
            break
        prefix.append(column[0])
    if len(prefix) == len(same[0]):  # hammasi bir xil (takror xat) — tartib raqami noma'lum
        prefix = []
    return Template(common, "".join(prefix))


def matches(number: str, template: Template) -> bool:
    """Raqam qolipga mosmi: tuzilishi bir xil va tashkilotning bosh qismi bilan boshlanadi."""
    value = key(number)
    return structure(value) == template.structure and value.startswith(template.prefix)


def fit(number: str, template: Template) -> str:
    """Raqamni qolipga moslaydi (mos kelmasa — o'zgarishsiz, key ko'rinishida):
    1) guruhlar soni mos, faqat ajratgich turi farq qilsa — ajratgichlar qolipdagidek;
    2) tuzilish mos va bosh qism guruhlari bir xil uzunlikda bo'lsa — bosh qism tashkilotniki;
    3) ajratgichlarsiz bosh qism raqamlari mos bo'lsa (ajratgich tushib qolgan) — bosh qism
       tiklanadi."""
    value = key(number)
    parts = PART.findall(value)
    wanted = [c for c in template.structure if c in SEPARATORS]
    have = [i for i, part in enumerate(parts) if part in SEPARATORS]
    if len(have) == len(wanted) and skeleton(structure(value)) == skeleton(template.structure):
        for i, separator in zip(have, wanted, strict=True):
            parts[i] = separator
        value = "".join(parts)
    if not template.prefix:
        return value
    head = PART.findall(template.prefix)
    parts = PART.findall(value)
    if structure(value) == template.structure and all(
        len(a) == len(b) for a, b in zip(parts, head, strict=False)
    ):
        return template.prefix + "".join(parts[len(head) :])
    if bare(value).startswith(bare(template.prefix)):
        rest, need = value, len(bare(template.prefix))
        while need:  # bosh qism raqamlarini (ajratgichlari bilan) tashlab o'tamiz
            need -= rest[0] not in SEPARATORS
            rest = rest[1:]
        return template.prefix + rest.lstrip(SEPARATORS)
    return value


def fit_all(numbers: dict[str, str | None], template: Template | None) -> dict[str, str | None]:
    """Bitta OCR'ning hamma raqamlari qolipga moslangan (qolip bo'lmasa yoki tuzatish kerak
    bo'lmasa — o'qilgan ko'rinishi qoladi: katta harflar va bo'shliqlar xodimga shundayligicha)."""
    if template is None:
        return numbers
    return {crop: fitted(value, template) for crop, value in numbers.items()}


def fitted(value: str | None, template: Template) -> str | None:
    if not value:
        return value
    result = fit(value, template)
    return value if result == key(value) else result
