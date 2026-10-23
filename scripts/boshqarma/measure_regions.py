"""B4.2: hududni topish sifatini dev xatlarda o'lchash. Ekranga FAQAT raqamlar va hudud kalitlari.

Xato xatlar ro'yxati outputs/b4_hudud_xatolar.csv ga yoziladi (gitignore'da, faqat Ibrohim uchun):
ularni scripts/data/show_text.py bilan ochib, xato sababini ko'rish mumkin.

Matn keshdan olinadi (B3.4): avval `poetry run python -m scripts.text.build_cache`.
Ishga tushirish: poetry run python -m scripts.boshqarma.measure_regions
"""

import csv
from collections import Counter
from pathlib import Path

from src.common.schema import expected_boshqarma, group_of
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.boshqarma import choose_region, letter_regions
from src.fields.regions import region_of_boshqarma

VARIANTS = {
    "A. hamma matn, chetlashsiz": dict(recipient_mode="keep", drop_ministry=False),
    "C. o'ng blok butunlay chetda": dict(recipient_mode="drop"),
    "E. o'ng blokdan faqat Toshkent": dict(recipient_mode="tashkent"),
    # Rahbar: asosiy ma'lumot 1–2-sahifada, aniqlik uchun 1–4 olsa ham bo'ladi, qolgani ilova
    "D. C, faqat 1–2-sahifa": dict(recipient_mode="drop", max_pages=2),
    "F. C, faqat 1–4-sahifa": dict(recipient_mode="drop", max_pages=4),
    "G. C, faqat 1–6-sahifa (tanlangan)": dict(recipient_mode="drop", max_pages=6),
}
MAIN_VARIANT = "C. o'ng blok butunlay chetda"
ERRORS_FILE = Path("outputs/b4_hudud_xatolar.csv")


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    outcomes = {name: Counter() for name in VARIANTS}
    confusion, per_region = Counter(), Counter()
    other_groups = Counter()  # notariat/xalqaro xatlarida hudud topildimi
    errors = []

    for doc_id in load_split()["dev"]:
        expected = expected_boshqarma(load_truth(letters[doc_id]))
        group, region = group_of(expected), region_of_boshqarma(expected)
        pages = get_pages(letters[doc_id])
        for name, options in VARIANTS.items():
            hits = letter_regions(pages, **options)
            chosen = choose_region(hits)
            if group != "viloyat":
                if name == MAIN_VARIANT:
                    other_groups[(group, "hudud topildi" if hits else "hudud yo'q")] += 1
                continue
            if chosen == region:
                outcome = "to'g'ri"
            elif chosen is None:
                outcome = "topilmadi"
            else:
                outcome = "noto'g'ri"
            outcomes[name][outcome] += 1
            outcomes[name]["ro'yxatda bor"] += region in {h.key for h in hits}
            if name == MAIN_VARIANT:
                per_region[(region, outcome == "to'g'ri")] += 1
                if outcome != "to'g'ri":
                    confusion[(region, chosen)] += 1
                    found = "; ".join(f"{h.key}:{h.weight}«{h.text}»" for h in hits)
                    errors.append([doc_id, region, chosen, outcome, found])

    n = sum(outcomes[MAIN_VARIANT][k] for k in ("to'g'ri", "topilmadi", "noto'g'ri"))
    print(f"B4.2: hududni topish, dev viloyat xatlari ({n} ta)\n")
    header = ["to'g'ri", "topilmadi", "noto'g'ri", "ro'yxatda bor"]
    print(f"  {'':<38}" + "".join(f"{h:>15}" for h in header))
    for name, counts in outcomes.items():
        cells = "".join(f"{counts[h]:>4} ({counts[h] / n:4.0%})".rjust(15) for h in header)
        print(f"  {name:<38}{cells}")

    print(f"\n  {MAIN_VARIANT} — hudud bo'yicha (to'g'ri / jami):")
    for region in sorted({r for r, _ in per_region}, key=str):
        ok = per_region[(region, True)]
        total = ok + per_region[(region, False)]
        print(f"    {str(region):<14} {ok:>2} / {total}")
    if confusion:
        print(f"\n  {MAIN_VARIANT} — xatolar (kutilgan -> topilgan):")
        for (want, got), count in confusion.most_common():
            print(f"    {want} -> {got}: {count}")

    print("\n  Notariat va xalqaro xatlarida hudud topildimi (B4.3 uchun):")
    for (group, found), count in sorted(other_groups.items()):
        print(f"    {group:<9} {found:<14} {count}")

    ERRORS_FILE.parent.mkdir(exist_ok=True)
    with ERRORS_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["doc_id", "kutilgan", "topilgan", "natija", "topilmalar"])
        writer.writerows(errors)
    print(f"\n  {len(errors)} ta xato xat ro'yxati (faqat o'zingiz uchun): {ERRORS_FILE}")


if __name__ == "__main__":
    main()
