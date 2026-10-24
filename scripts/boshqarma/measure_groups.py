"""B4.3: boshqarma guruhini (notariat / viloyat) aniqlash — dev xatlarda 3 ta notariat qoidasi.

To'g'ri: notariat xati notariat deb topilgan yoki viloyat xati to'g'ri hudud bilan topilgan.
"tekshirish kerak": AI javob bermagan (notariat belgisi ham, hudud ham yo'q).
Ekranga FAQAT raqamlar chiqadi. Matn keshdan olinadi (B3.4).

Ishga tushirish: poetry run python -m scripts.boshqarma.measure_groups
"""

from collections import Counter

from src.common.schema import expected_boshqarma, group_of
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.boshqarma import (
    NOTARY_MODES,
    REGION_PAGES,
    REGISTRY,
    predict_group,
    recipient_and_body,
)
from src.fields.regions import prepare, region_of_boshqarma

NAMES = {
    "mention": "N1 нотари…",
    "no_copies": "N2 nusxasiz",
    "inheritance": "N3 +meros",
}
COLUMNS = ["notariat", "viloyat", "xalqaro", None]


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    data = []
    for doc_id in load_split()["dev"]:
        expected = expected_boshqarma(load_truth(letters[doc_id]))
        data.append((group_of(expected), region_of_boshqarma(expected), get_pages(letters[doc_id])))

    n = len(data)
    print(f"B4.3: boshqarma guruhi, dev {n} xat\n")
    print(f"  {'variant':<14}{'to`g`ri':>13}{'tekshirish kerak':>19}{'noto`g`ri':>13}")
    confusions = {}
    for mode in NOTARY_MODES:
        outcome, confusion = Counter(), Counter()
        for group, region, pages in data:
            got_group, got_region = predict_group(pages, mode)
            confusion[(group, got_group)] += 1
            if got_group is None:
                outcome["kerak"] += 1
            elif got_group == group and (group == "notariat" or got_region == region):
                outcome["ok"] += 1
            else:
                outcome["xato"] += 1
        confusions[mode] = confusion
        cells = [f"{outcome[k]:>3} ({outcome[k] / n:4.0%})" for k in ("ok", "kerak", "xato")]
        print(f"  {NAMES[mode]:<14}{cells[0]:>13}{cells[1]:>19}{cells[2]:>13}")

    # B5.7c: hudud ham, notariat ham yo'q (javobsiz) xatlar — ЗАГС so'zlari bormi (1–6-sahifa)?
    # Gipoteza: viloyat xati deyarli doim ЗАГС hujjatini so'raydi, xalqaro — yo'q.
    unanswered = Counter()
    for group, _, pages in data:
        if predict_group(pages) == (None, None):
            body = prepare(recipient_and_body(pages, REGION_PAGES)[1])
            unanswered[group, "ЗАГС bor" if REGISTRY.search(body) else "ЗАГС yo'q"] += 1
    print("\n  Javobsiz xatlar (hudud ham, notariat ham yo'q) — ЗАГС so'zlari, 1–6-sahifa:")
    for (group, registry), count in sorted(unanswered.items()):
        print(f"    {group:<10} {registry:<10} {count}")

    for mode in NOTARY_MODES:
        print(f"\n  {NAMES[mode]} — kutilgan guruh (qator) va AI javobi (ustun):")
        print(f"    {'':<10}" + "".join(f"{str(c or 'tekshirish'):>12}" for c in COLUMNS))
        for group in ("notariat", "viloyat", "xalqaro"):
            row = "".join(f"{confusions[mode][(group, c)]:>12}" for c in COLUMNS)
            print(f"    {group:<10}{row}")


if __name__ == "__main__":
    main()
