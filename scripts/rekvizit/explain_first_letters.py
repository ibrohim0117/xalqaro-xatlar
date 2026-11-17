"""Jo'natuvchi: tashkilotning BIRINCHI xati — takliflar nega to'g'ri nomni bermaydi.

simulate_arrival (B) bilan bir xil: yangi 150 xat kelish tartibida, model — eski 100 va oldin
kelgan yangi xatlarning hammasidan. Tashkilot xotirada yo'q xatlarni (yangi 150 da 36 ta) xotira
topa olmaydi: blankdan yasalgan nom variantlari (sender_variants) va o'xshash tanish tashkilotlar
taklif qilinadi — bir bosishda 10/36. Har birida:
  - to'g'ri nom turi (explain_senders.family) va skeleti (qolip so'zlari ochiq, joy nomlari "…");
  - eng yaqin taklif (yoki yozilgan qiymat) o'xshashligi (fuzz.ratio, 0..1) va uning skeleti;
  - xotiradagi eng yaqin nom o'xshashligi: 0.90 dan yuqori — bitta tashkilot boshqacha yozilgan
    bo'lishi mumkin (haqiqiy yangi emas);
  - blankda nima topilgan (davlat, hudud, tashkilot turi so'zlari);
  - "variantlar bilan": nom yozilganda (xato bo'lsa ham) variantlar taklif qilinmaydi — agar ular
    doim taklif qilinsa, bir bosishda nechta bo'lardi.
Ekranga FAQAT turlar, skeletlar, sonlar va DOC raqamlari (nomlar emas).

Ishga tushirish: poetry run python -m scripts.rekvizit.explain_first_letters [--ids]
"""

import argparse
from collections import Counter

from rapidfuzz import fuzz

from scripts.data.sample_new import new_root
from scripts.rekvizit.explain_senders import blank_parts, family, skeleton
from scripts.rekvizit.simulate_arrival import (
    FIELD,
    arrival_order,
    grown,
    load,
    same,
    sender_outcome,
)
from src.common.text import normalize
from src.engine.pipeline import MAX_PAGES
from src.engine.predict import predict
from src.evaluation.dataset import list_letters
from src.fields.sender_variants import page_variants

NEAR = 0.90  # shundan yuqori o'xshashlik — deyarli bir xil nom (yozilishi farq qiladi)
BUCKETS = ((NEAR, f">= {NEAR:.2f}"), (0.75, "0.75–0.90"), (0.0, "< 0.75"))


def best_match(name: str, options: list[str]) -> tuple[float, str | None]:
    """(eng yuqori o'xshashlik 0..1, eng yaqin variant) — normalize qilingan matnlarda."""
    scored = [(fuzz.ratio(normalize(o), normalize(name)) / 100, o) for o in options if o]
    return max(scored, default=(0.0, None))


def bucket(similarity: float) -> str:
    return next(label for floor, label in BUCKETS if similarity >= floor)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", action="store_true", help="har xat: tur, skeletlar, o'xshashlik")
    args = parser.parse_args()
    old = load(list_letters(), "eski")
    new = arrival_order(load(list_letters(new_root()), "yangi"))
    seen = {normalize(item.sender) for item in old if item.sender}
    families, misses, rows = Counter(), Counter(), []
    for i, item in enumerate(new):
        name = normalize(item.sender)
        if not name or name in seen:
            seen.add(name)
            continue
        seen.add(name)
        model = grown(old, new[:i])
        answer = predict(item.pages[:MAX_PAGES], model)
        kind, one_click = sender_outcome(answer, item.sender)
        written = answer["rekvizit_document"][FIELD]
        variants = page_variants(item.pages)
        options = [*(answer["takliflar"].get(FIELD) or []), written, *variants]
        similarity, best = best_match(item.sender, options)
        memory, _ = best_match(item.sender, sorted(set(model.sender_names)))
        with_variants = one_click or any(same(v, item.sender) for v in variants)
        kind_of = family(item.sender)
        families[kind_of, "xat"] += 1
        families[kind_of, "bir bosishda"] += one_click
        families[kind_of, "variant yasaldi"] += bool(variants)
        families[kind_of, "variantlar bilan"] += with_variants
        if not with_variants:
            misses["eng yaqin taklif " + (bucket(similarity) if best else "— taklif yo'q")] += 1
            misses["xotirada deyarli bir xil nom (>= 0.90)"] += memory >= NEAR
            misses["blank: " + blank_parts(item.pages)] += 1
        rows.append(
            f"{item.doc_id} [{'bir bosishda' if one_click else kind}"
            f"{', variantlar bilan bir bosishda' if with_variants and not one_click else ''}] "
            f"{kind_of}: "
            f"to'g'ri '{skeleton(item.sender)}'; eng yaqin '{skeleton(best) if best else '—'}' "
            f"({similarity:.2f}); xotira {memory:.2f}; {blank_parts(item.pages)}"
        )

    print("\r" + " " * 40 + "\r", end="")
    kinds = sorted({k for k, _ in families}, key=lambda k: -families[k, "xat"])
    total = sum(families[k, "xat"] for k in kinds)
    found = sum(families[k, "variantlar bilan"] for k in kinds)
    print(f"Jo'natuvchi — tashkilotning birinchi xati (yangi 150, kelish tartibida): {total} xat\n")
    head = "to'g'ri nom turi"
    columns = ("xat", "bir bosishda", "variant yasaldi", "variantlar bilan")
    print(f"  {head:<28}" + "".join(f"{c:>18}" for c in columns))
    for kind_of in kinds:
        print(f"  {kind_of:<28}" + "".join(f"{families[kind_of, c]:>18}" for c in columns))
    print(f"  {'jami':<28}" + "".join(f"{sum(families[k, c] for k in kinds):>18}" for c in columns))
    print(f"\n  Variantlar bilan ham bir bosishda topilmaganlar ({total - found} xat):")
    for label, count in sorted(misses.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"    {label:<60}{count:>4}")
    if args.ids:
        print("\n  Har xat:")
        for row in rows:
            print(f"    {row}")


if __name__ == "__main__":
    main()
