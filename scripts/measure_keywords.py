"""B4.3: qaysi so'zlar notariat va xalqaro xatlarini viloyat xatlaridan ajratadi?

Har bir nomzod so'z har guruhda nechta xatda uchrashi sanaladi — 1–2-sahifada va hamma sahifada.
Yaxshi kalit so'z: notariatda (yoki xalqaroda) ko'p, viloyatda kam.
Ekranga FAQAT umumiy so'zlar va sonlar chiqadi. Matn keshdan olinadi (B3.4).

Ishga tushirish: poetry run python -m scripts.measure_keywords
"""

import re
from collections import Counter

from src.boshqarma import recipient_and_body
from src.dataset import expected_boshqarma, group_of, list_letters, load_split, load_truth
from src.regions import prepare
from src.text_cache import get_pages

GROUPS = ["viloyat", "notariat", "xalqaro"]
# Nomzodlar: notariat (meros, notarius), FHDYO, sud ishlari va umumiy so'zlar (taqqoslash uchun)
CANDIDATES = {
    "нотари…": r"нотари",
    "наследств…": r"наследств",
    "наследник…": r"наследник",
    "наследодател…": r"наследодател",
    "завещ…": r"завещ",
    "доверенност…": r"доверенност",
    "имуществ…": r"имуществ",
    "недвижим…": r"недвижим",
    "meros / мерос": r"\bmeros|\bмерос",
    "notar… (lotin)": r"notar",
    "загс / актовая запись": r"загс|актов\w*\s+запис",
    "свидетельств…": r"свидетельств",
    "истребов…": r"истребов",  # истребование, истребовать
    "вруч…": r"вруч",  # вручение, вручить
    "суд…": r"\bсуд",
    "алимент…": r"алимент",
    "розыск…": r"розыск",
    "апостил…": r"апостил",
    "гражданств…": r"гражданств",
    "конвенци…": r"конвенци",
    "правовой помощи": r"правов\w*\s+помощ",
}
COMPILED = {name: re.compile(pattern) for name, pattern in CANDIDATES.items()}


def keywords_in(text: str) -> set[str]:
    """Matnda uchragan nomzod so'zlar."""
    low = prepare(text)
    return {name for name, pattern in COMPILED.items() if pattern.search(low)}


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    sizes = Counter()
    first, everywhere = Counter(), Counter()  # (so'z, guruh) -> nechta xatda
    for doc_id in load_split()["dev"]:
        group = group_of(expected_boshqarma(load_truth(letters[doc_id])))
        pages = get_pages(letters[doc_id])
        sizes[group] += 1
        for name in keywords_in(recipient_and_body(pages, max_pages=2)[1]):
            first[(name, group)] += 1
        for name in keywords_in(recipient_and_body(pages)[1]):
            everywhere[(name, group)] += 1

    print(
        "B4.3: nomzod so'zlar qaysi guruhda nechta xatda uchraydi (dev, qabul qiluvchi blokisiz)\n"
    )
    head = "".join(f"{g} ({sizes[g]})".rjust(15) for g in GROUPS)
    print(f"  {'':<24}{'— 1–2-sahifa —':^45}  {'— hamma sahifa —':^45}")
    print(f"  {'so`z':<24}{head}  {head}")
    for name in CANDIDATES:
        cells = [
            f"{counter[(name, g)]:>3}/{sizes[g]:<3}".rjust(15)
            for counter in (first, everywhere)
            for g in GROUPS
        ]
        print(f"  {name:<24}{''.join(cells[:3])}  {''.join(cells[3:])}")


if __name__ == "__main__":
    main()
