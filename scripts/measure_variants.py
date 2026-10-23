"""B5.1c-3: tarjima variantlari dev'da — xodim yozgan nom variantlar orasida bormi?

Har dev xati go'yo NOTANISH deb olinadi: blankdan variantlar yasaladi va json'dagi nom bilan
solishtiriladi. Alohida — haqiqatan notanish (dev'da bir marta uchragan) jo'natuvchilar.
Ekranga sonlar va topilmaganlar uchun "xodim nomi | eng yaqin variant" chiqadi — faqat jo'natuvchi
tashkilot nomlari (ochiq davlat tashkilotlari; Ibrohim ruxsati, CLAUDE.md). Matn keshdan olinadi.

Ishga tushirish: poetry run python -m scripts.measure_variants
"""

from collections import Counter

from rapidfuzz import fuzz

from scripts.measure_senders import sender_of
from src.dataset import list_letters, load_split, load_truth
from src.evaluate import normalize
from src.sender_variants import page_variants
from src.text_cache import get_pages


def check(name: str, variants: list[str]) -> tuple[str, float, str]:
    """(natija, eng yaxshi o'xshashlik, eng yaqin variant)."""
    if not variants:
        return "variant yo'q", 0.0, ""
    keys = [normalize(v) for v in variants]
    target = normalize(name)
    best = max(variants, key=lambda v: fuzz.ratio(normalize(v), target))
    similarity = fuzz.ratio(normalize(best), target) / 100
    if keys[0] == target:
        return "1-variant to'g'ri", similarity, best
    if target in keys:
        return "2–4-variantda bor", similarity, best
    return "variantlarda yo'q", similarity, best


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = load_split()["dev"]
    rows = []
    for doc_id in dev:
        name = sender_of(load_truth(letters[doc_id]))
        rows.append((name, *check(name, page_variants(get_pages(letters[doc_id])))))
    counts = Counter(normalize(name) for name, *_ in rows)

    groups = {
        "hamma 70 xat (go'yo notanish)": rows,
        "haqiqatan notanish (dev'da 1 marta)": [r for r in rows if counts[normalize(r[0])] == 1],
    }
    order = ["1-variant to'g'ri", "2–4-variantda bor", "variantlarda yo'q", "variant yo'q"]
    print("B5.1c-3: tarjima variantlari, dev\n")
    for title, items in groups.items():
        outcome = Counter(r[1] for r in items)
        sims = [r[2] for r in items if r[1] != "variant yo'q"]
        avg = f"{sum(sims) / len(sims):.2f}" if sims else "—"
        print(f"  {title}: {len(items)} xat, eng yaqin variant o'xshashligi o'rtacha {avg}")
        for key in order:
            print(f"    {key:<22} {outcome[key]:>3}")
        print()

    print("  Topilmaganlar (har tashkilot bir marta): xodim nomi | eng yaqin variant | o'xshashlik")
    shown = set()
    for name, outcome, sim, best in rows:
        if outcome in ("variantlarda yo'q", "variant yo'q") and normalize(name) not in shown:
            shown.add(normalize(name))
            print(f"    {name}\n      → {best or '(variant yo`q)'} | {sim:.2f}")


if __name__ == "__main__":
    main()
