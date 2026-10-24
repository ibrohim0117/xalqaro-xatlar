"""B4.2: hududni topish sifatini dev xatlarda o'lchash. Ekranga FAQAT raqamlar va hudud kalitlari.

Xato xatlar ro'yxati outputs/b4_hudud_xatolar.csv ga yoziladi (gitignore'da, faqat Ibrohim uchun):
ularni scripts/data/show_text.py bilan ochib, xato sababini ko'rish mumkin.

B5.7: TANLASH variantlari (nomzodlar G bilan bir xil, faqat hudud boshqacha tanlanadi) — FHDYO
hujjati so'ralganda hal qiluvchi joy hujjat qayd etilgan FHDYO (ЗАГС) bo'limi:
  H — "ЗАГС"/"запись акта"/"ФХДЁ" ga yaqin (±80 belgi) eslatma og'irligi ×3; I — xuddi shu, ±200;
  J — ЗАГС yonida hudud bo'lsa, faqat o'shalar orasidan; K — 1–2-sahifadagi eslatmalar ×2.
G ga nisbatan "tuzatildi" va "buzildi" — DOC raqamlari bilan.
Prototip (J — boshqarma.near_registry) ham sanaladi: o'lchov bilan bir xil bo'lishi kerak.
Sinab, rad etilgan (B5.7, natijasi CLAUDE.md da): hudud topilmagan 5 xatda o'ng blok zaxirasi (0) va
fuzzy o'zak qidiruvi (0 to'g'ri, 2 xato, aniq xatlarda shovqin 7/51) — bu xatlarning hammasida ЗАГС
yonida joy so'zi bor, lekin O'zbekiston hududi emas (ehtimol chet el ЗАГС'i).
Matn keshdan olinadi (B3.4): avval `poetry run python -m scripts.text.build_cache`.
Ishga tushirish: poetry run python -m scripts.boshqarma.measure_regions
"""

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from src.common.schema import expected_boshqarma, group_of
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.boshqarma import (
    choose_region,
    letter_regions,
    near_registry,
    recipient_and_body,
)
from src.fields.regions import Hit, prepare, region_of_boshqarma

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
CHOSEN = "G. C, faqat 1–6-sahifa (tanlangan)"
REGISTRY = re.compile(r"загс|запис\w*\s+акт|актов\w*\s+запис|фхд|fhdy")
# nom -> (ЗАГС oynasi belgida yoki None, og'irlik, faqat ЗАГС yonidagilar, 1–2-sahifa ×)
CHOOSERS = {
    "H. G + ЗАГС yonida (±80) ×3": (80, 3, False, 1),
    "I. G + ЗАГС yonida (±200) ×3": (200, 3, False, 1),
    "J. G, ЗАГС yonidagilar orasidan": (200, 1, True, 1),
    "K. G + 1–2-sahifa ×2": (None, 1, False, 2),
}


def choose_weighted(
    hits: list[Hit], pages: list, window: int | None, bonus: int, only_near: bool, early: int
) -> str | None:
    """choose_region kabi, lekin ЗАГС yonidagi va 1–2-sahifadagi eslatmalar og'irroq."""
    recipient, body = recipient_and_body(pages, 6)
    offset = len(prepare(recipient)) + 1  # letter_regions body topilmalarini shuncha suradi
    low = prepare(body)
    registry = [m.start() + offset for m in REGISTRY.finditer(low)]
    early_end = offset + len(prepare("\n".join(p.main.text for p in pages[:2])))

    def near(hit: Hit) -> bool:
        return window is not None and any(abs(hit.start - pos) <= window for pos in registry)

    if only_near and any(near(h) for h in hits):
        hits = [h for h in hits if near(h)]
    score: dict[str, int] = defaultdict(int)
    first: dict[str, int] = {}
    for hit in hits:
        weight = hit.weight * (bonus if near(hit) else 1) * (early if hit.start < early_end else 1)
        score[hit.key] += weight
        first.setdefault(hit.key, hit.start)
    return max(score, key=lambda key: (score[key], -first[key])) if score else None


ERRORS_FILE = Path("outputs/b4_hudud_xatolar.csv")


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    outcomes = {name: Counter() for name in [*VARIANTS, *CHOOSERS]}
    prototype_ok = 0  # B5.7: prototip (J)
    changed = defaultdict(list)  # (variant, "tuzatildi" | "buzildi") -> DOC
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
        if group != "viloyat":
            continue
        hits = letter_regions(pages, **VARIANTS[CHOSEN])
        base = choose_region(hits)
        for name, options in CHOOSERS.items():
            chosen = choose_weighted(hits, pages, *options)
            if chosen is None:
                outcomes[name]["topilmadi"] += 1
            else:
                outcomes[name]["to'g'ri" if chosen == region else "noto'g'ri"] += 1
            outcomes[name]["ro'yxatda bor"] += region in {h.key for h in hits}
            if (chosen == region) != (base == region):
                changed[name, "tuzatildi" if chosen == region else "buzildi"].append(doc_id)
        prototype_ok += choose_region(near_registry(pages, hits) or hits) == region

    n = sum(outcomes[MAIN_VARIANT][k] for k in ("to'g'ri", "topilmadi", "noto'g'ri"))
    print(f"B4.2: hududni topish, dev viloyat xatlari ({n} ta)\n")
    header = ["to'g'ri", "topilmadi", "noto'g'ri", "ro'yxatda bor"]
    print(f"  {'':<38}" + "".join(f"{h:>15}" for h in header))
    for name, counts in outcomes.items():
        cells = "".join(f"{counts[h]:>4} ({counts[h] / n:4.0%})".rjust(15) for h in header)
        print(f"  {name:<38}{cells}")

    print(f"\n  B5.7 tanlash variantlari — {CHOSEN[:2]} ga nisbatan:")
    for name in CHOOSERS:
        fixed, broken = changed[name, "tuzatildi"], changed[name, "buzildi"]
        print(f"    {name:<34} tuzatildi {len(fixed)}: {', '.join(fixed) or '—'}")
        print(f"    {'':<34} buzildi   {len(broken)}: {', '.join(broken) or '—'}")
    print(f"  Prototip (J, boshqarma.near_registry): to'g'ri {prototype_ok}/{n}")

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
