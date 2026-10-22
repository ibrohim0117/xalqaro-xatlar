"""B4.2: hududni topish sifatini dev xatlarda o'lchash. Ekranga FAQAT raqamlar va hudud kalitlari.

Matn keshdan olinadi (B3.4): avval `poetry run python -m scripts.build_cache`.
Ishga tushirish: poetry run python -m scripts.measure_regions
"""

from collections import Counter

from src.boshqarma import choose_region, letter_regions, region_text
from src.dataset import expected_boshqarma, group_of, list_letters, load_split, load_truth
from src.regions import region_of_boshqarma
from src.text_cache import get_pages

VARIANTS = {
    "A. hamma matn, chetlashsiz": lambda p: letter_regions(
        region_text(p, drop_recipient=False), drop_ministry=False
    ),
    "B. + o'ng yuqori blok": lambda p: letter_regions(region_text(p), drop_ministry=False),
    "C. + vazirlik manzili": lambda p: letter_regions(region_text(p)),
    "D. C, faqat 1-2 sahifa": lambda p: letter_regions(region_text(p, max_pages=2)),
}
MAIN_VARIANT = "C. + vazirlik manzili"


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    outcomes = {name: Counter() for name in VARIANTS}
    confusion, per_region = Counter(), Counter()
    other_groups = Counter()  # notariat/xalqaro xatlarida hudud topildimi

    for doc_id in load_split()["dev"]:
        expected = expected_boshqarma(load_truth(letters[doc_id]))
        group, region = group_of(expected), region_of_boshqarma(expected)
        pages = get_pages(letters[doc_id])
        for name, find in VARIANTS.items():
            hits = find(pages)
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
                if outcome == "noto'g'ri":
                    confusion[(region, chosen)] += 1

    n = sum(outcomes[MAIN_VARIANT][k] for k in ("to'g'ri", "topilmadi", "noto'g'ri"))
    print(f"B4.2: hududni topish, dev viloyat xatlari ({n} ta)\n")
    header = ["to'g'ri", "topilmadi", "noto'g'ri", "ro'yxatda bor"]
    print(f"  {'':<28}" + "".join(f"{h:>15}" for h in header))
    for name, counts in outcomes.items():
        cells = "".join(f"{counts[h]:>4} ({counts[h] / n:4.0%})".rjust(15) for h in header)
        print(f"  {name:<28}{cells}")

    print(f"\n  {MAIN_VARIANT} — hudud bo'yicha (to'g'ri / jami):")
    for region in sorted({r for r, _ in per_region}, key=str):
        ok, total = (
            per_region[(region, True)],
            per_region[(region, True)] + per_region[(region, False)],
        )
        print(f"    {str(region):<14} {ok:>2} / {total}")
    if confusion:
        print(f"\n  {MAIN_VARIANT} — xatolar (kutilgan -> topilgan):")
        for (want, got), count in confusion.most_common():
            print(f"    {want} -> {got}: {count}")

    print("\n  Notariat va xalqaro xatlarida hudud topildimi (B4.3 uchun):")
    for (group, found), count in sorted(other_groups.items()):
        print(f"    {group:<9} {found:<14} {count}")


if __name__ == "__main__":
    main()
