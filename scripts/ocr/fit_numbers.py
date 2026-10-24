"""B5.5-3: tashkilot raqam qolipi — o'lchov (src/fields/number_template). OCR qayta ishlatilmaydi.

Har dev xat uchun qolip shu tashkilotning BOSHQA dev xatlari raqamlaridan (json) o'rganiladi — xat
o'zidan o'rganmaydi; test xatlariga tegilmaydi. Tashkilot — json'dagi jo'natuvchi nomi.
1) Qolip qanchalik doimiy: nechta xatga qolip topildi; to'g'ri raqam qolip tuzilishidami
   (9/9-9/9); bosh qismi qolipdagidek boshlanadimi.
2) VLM (aniq savol) har ko'rinishi — header, line, page, number: qolipga moslashdan oldin va keyin
   nechta to'g'ri; nechtasi tuzatildi, nechtasi BUZILDI (to'g'ri edi — noto'g'ri bo'ldi).
3) Yuqori chegara: to'g'ri raqam VLM ko'rinishlaridan birida — oldin va qolip bilan.
Ekranga FAQAT sonlar; --show-ids — tuzatilgan va buzilgan DOC raqamlari. --reader — qaysi OCR
matnlari (standart vlm-extract; 4B sinovi: vlm-extract-4b), --ids — faqat shu xatlar (qolip baribir
hamma dev xatlardan, xatning o'zisiz).

Ishga tushirish: poetry run python -m scripts.ocr.fit_numbers [--show-ids] [--reader R] [--ids …]
"""

import argparse
import json
from collections import Counter, defaultdict

from scripts.ocr.compare_ocr import OUT_DIR
from src.common.text import normalize
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.fields.number_template import Template, fit, learn, structure
from src.fields.number_vote import engine_numbers, key

VIEWS = ("header", "line", "page", "number")  # VLM aniq savol o'qigan bo'laklar


def templates(truths: dict[str, dict]) -> dict[str, Template | None]:
    """Har xat uchun qolip — shu tashkilotning BOSHQA xatlari raqamlaridan (xat o'zi kirmaydi)."""
    sender = {d: normalize(t.get("hujjat_junatuvchi_tashkilot")) for d, t in truths.items()}
    letters_of = defaultdict(list)
    for doc_id, name in sender.items():
        letters_of[name].append(doc_id)
    return {
        doc_id: learn(
            [truths[other].get("hujjat_raqami") for other in letters_of[name] if other != doc_id]
        )
        for doc_id, name in sender.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show-ids", action="store_true", help="tuzatilgan va buzilganlar")
    parser.add_argument("--reader", default="vlm-extract", help="qaysi OCR matnlari")
    parser.add_argument("--ids", nargs="+", help="faqat shu xatlar (DOC_…)")
    args = parser.parse_args()
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    truths = {d: load_truth(letters[d]).get("rekvizit_document") or {} for d in dev}
    learned = templates(truths)
    saved = json.loads((OUT_DIR / f"{args.reader}.json").read_text(encoding="utf-8"))
    senders = Counter(normalize(t.get("hujjat_junatuvchi_tashkilot")) for t in truths.values())
    stats, views, changed = Counter(), defaultdict(Counter), defaultdict(list)
    for doc_id in [d for d in dev if not args.ids or d in set(args.ids)]:
        truth = truths[doc_id].get("hujjat_raqami")
        if not truth:
            continue
        stats["xat"] += 1
        template = learned[doc_id]
        if template:
            stats["qolip"] += 1
            stats["tuzilish mos"] += structure(truth) == template.structure
            if template.prefix:
                stats["bosh qism bor"] += 1
                stats["bosh qism mos"] += key(truth).startswith(template.prefix)
        any_before = any_after = False
        for view, value in engine_numbers(saved.get(doc_id, {})).items():
            if view not in VIEWS or not value:
                continue
            before = key(value) == key(truth)
            after = key(fit(value, template)) == key(truth) if template else before
            count = views[view]
            count["javob"] += 1
            count["oldin"] += before
            count["keyin"] += after
            if after != before:
                kind = "tuzatildi" if after else "buzildi"
                count[kind] += 1
                changed[view, kind].append(doc_id)
            any_before |= before
            any_after |= after
        stats["chegara oldin"] += any_before
        stats["chegara keyin"] += any_after

    n, with_template = stats["xat"], stats["qolip"]
    many = sum(c >= 3 for c in senders.values())
    print(f"Raqam qolipi ({args.reader}): {n} xat; dev'da {len(senders)} tashkilot", end="")
    print(f" (3 va undan ko'p xatli: {many})\n")
    print(f"  1) Qolip (tashkilotning kamida 2 ta boshqa xatidan): {with_template}/{n} xatda")
    print(f"     to'g'ri raqam qolip tuzilishida: {stats['tuzilish mos']}/{with_template}")
    print(
        f"     doimiy bosh qism bor: {stats['bosh qism bor']}; to'g'ri raqam shu bilan boshlanadi: "
        f"{stats['bosh qism mos']}/{stats['bosh qism bor']}"
    )
    print("\n  2) VLM (aniq savol) ko'rinishlari — qolipga moslashdan oldin va keyin to'g'ri:")
    head = f"{'javob':>7}{'oldin':>7}{'keyin':>7}{'tuzatildi':>11}{'buzildi':>9}"
    print(f"     {'ko`rinish':<10}{head}")
    for view in VIEWS:
        c = views[view]
        print(
            f"     {view:<10}{c['javob']:>7}{c['oldin']:>7}{c['keyin']:>7}"
            f"{c['tuzatildi']:>11}{c['buzildi']:>9}"
        )
    print(
        "\n  3) Yuqori chegara (VLM ko'rinishlaridan birida to'g'ri): "
        f"oldin {stats['chegara oldin']}, qolip bilan {stats['chegara keyin']}"
    )
    if args.show_ids:
        print("\n  O'zgargan xatlar (DOC raqamlari):")
        for (view, kind), docs in sorted(changed.items()):
            print(f"     {view} {kind} ({len(docs)}): {', '.join(docs)}")


if __name__ == "__main__":
    main()
