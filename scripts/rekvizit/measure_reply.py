"""B5.4: javob xatlar — "На № <raqam> от <sana>" qatori mazmun va boshqarmani yaxshilay oladimi.

Dev'da sanaladi:
1. json'dagi nostandart mazmunlardan nechtasi qolipda: "<sana>-yildagi <raqam>-son xat ijrosi
   bo'yicha";
2. "На №" qatori 1-sahifada bormi, to'lami, raqam/sana json'dagi mazmun bilan mosmi;
3. qoida "qator to'la (raqam va sana) bo'lsa — mazmun qolipda" qo'llansa, mazmun aniqligi qanday
   o'zgaradi (standart xatlarda yuzaga keladigan zarar ham hisobda);
4. javob xatlarda boshqarma (LOO javoblari, outputs/b4) va raqam boshidagi indeks -> boshqarma
   guruhi;
5. B5.6: reply.our_reference — xat matnida bizning raqam SHAKLI (boshqa javob xatlarning
   json'idan, xatning o'zisiz — halol), xatning o'z raqami chetlanadi, yonidagi sana: javob xatlarda
   aniq mosmi, oddiy xatlarda zarar, json raqami matnda umuman bormi (yuqori chegara), mazmun.
Ekranga FAQAT sonlar, indeks kodlari va guruh nomlari chiqadi. Matn keshdan olinadi.

Avval (boshqarma qismi uchun): poetry run python -m scripts.prototype.run_predict
Ishga tushirish:              poetry run python -m scripts.rekvizit.measure_reply
"""

import re
from collections import Counter, defaultdict
from pathlib import Path

from src.common.schema import expected_boshqarma, group_of
from src.common.text import most_common, normalize
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.evaluate import load_prediction, predicted_boshqarma
from src.evaluation.text_cache import get_pages
from src.fields.number_template import shape
from src.fields.reply import (
    our_reference,
    own_numbers,
    parse_reply_summary,
    reply_of,
    reply_summary,
)

PRED_DIR = Path("outputs/b4")


def same(a: str | None, b: str | None) -> bool:
    return bool(a) and normalize(a, spaceless=True) == normalize(b, spaceless=True)


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    truths = {d: load_truth(letters[d]) for d in dev}
    summary_of = {
        d: (t.get("rekvizit_document") or {}).get("hujjatning_qisqacha_mazmuni")
        for d, t in truths.items()
    }
    standard = most_common(list(summary_of.values()))[0]

    kinds, lines, in_template = Counter(), Counter(), Counter()
    harm, now_right, rule_right = 0, 0, 0
    ours = Counter()  # B5.6: bizning raqam shakli bo'yicha
    parsed = {d: parse_reply_summary(summary) for d, summary in summary_of.items()}
    reply_numbers = {d: found[1] for d, found in parsed.items() if found}
    boshqarma = Counter()
    index_groups: dict[str, Counter] = defaultdict(Counter)
    for doc_id in dev:
        truth, summary = truths[doc_id], summary_of[doc_id]
        is_standard = normalize(summary) == normalize(standard)
        template = parse_reply_summary(summary) if not is_standard else None  # (sana, raqam)
        kind = "standart" if is_standard else ("qolip" if template else "boshqa nostandart")
        kinds[kind] += 1

        pages = get_pages(letters[doc_id])[:6]  # AI shu sahifalarni o'qiydi (pipeline.MAX_PAGES)
        ref = reply_of(pages[0])
        # B5.6: shakllar — BOSHQA javob xatlardan (xatning o'zi kirmaydi)
        shapes = {shape(n) for other, n in reply_numbers.items() if other != doc_id}
        hit = our_reference(pages, own_numbers(pages[0]), shapes)
        if template:
            text = normalize(" ".join(page.main.text for page in pages), spaceless=True)
            ours["json raqami matnda bor"] += normalize(template[1], spaceless=True) in text
            ours["havola topildi"] += hit is not None
            if hit:
                ours["raqam mos"] += same(hit[0], template[1])
                ours["sana mos"] += same(hit[1], template[0])
        elif hit:
            ours["ZARAR"] += 1
        rule = reply_summary(*hit) if hit else standard
        ours["qoida bilan to'g'ri"] += normalize(rule) == normalize(summary)
        number, date = ref if ref else (None, None)
        line = (
            "yo'q" if ref is None else ("to'la (raqam o'qildi)" if number else "bo'sh / o'qilmadi")
        )
        lines[line] += 1

        if template:
            if ref is None or not number:
                in_template[f"qator {line}"] += 1
            else:
                in_template["raqam mos" if same(number, template[1]) else "raqam mos emas"] += 1
                in_template["sana ham mos" if same(date, template[0]) else "sana mos emas"] += 1
        filled = bool(number and date)
        if is_standard and filled:
            harm += 1
        # Qoida: qator to'la (raqam va sana) bo'lsa — qolip, aks holda standart mazmun
        rule = reply_summary(number, date) if filled else standard
        now_right += normalize(standard) == normalize(summary)
        rule_right += normalize(rule) == normalize(summary)

        if template or number:
            expected = expected_boshqarma(truth)
            predicted = predicted_boshqarma(load_prediction(PRED_DIR, doc_id))
            label = "javob xat (qolip)" if template else "qator to'la, mazmun standart"
            if not predicted:
                outcome = "topilmadi"
            else:
                outcome = "to'g'ri" if normalize(predicted) == normalize(expected) else "xato"
            boshqarma[(label, outcome)] += 1
            if number and (m := re.match(r"\d+", number)):
                index_groups[m[0]][group_of(expected)] += 1

    n = len(dev)
    print(f"B5.4: javob xatlar, dev {n} xat\n")
    print("  Mazmun (json):")
    for key in ("standart", "qolip", "boshqa nostandart"):
        print(f"    {key:<40} {kinds[key]:>3}")
    print("\n  'На №' qatori (1-sahifa, matn qatlami yoki OCR):")
    for key in ("yo'q", "bo'sh / o'qilmadi", "to'la (raqam o'qildi)"):
        print(f"    {key:<40} {lines[key]:>3}")
    print(f"\n  Qolipdagi {kinds['qolip']} xat:")
    for key, value in sorted(in_template.items()):
        print(f"    {key:<40} {value:>3}")
    print(f"\n  XAVF: standart mazmunli xatda qator to'la (qoida buzadi): {harm}")
    print(f"  Mazmun aniqligi: hozir {now_right}/{n} -> qoida bilan {rule_right}/{n}")
    print(f"\n  B5.6 bizning raqam shakli bo'yicha (1–6-sahifa); qolipdagi {kinds['qolip']} xat:")
    shapes_all = Counter(shape(n) for n in reply_numbers.values())
    print(
        f"    bizning raqamlar shakllari: {len(shapes_all)} xil — "
        + ", ".join(f"{s} {c}" for s, c in shapes_all.most_common())
    )
    for label in ("json raqami matnda bor", "havola topildi", "raqam mos", "sana mos"):
        print(f"    {label:<40} {ours[label]:>3}")
    print(f"  oddiy xatlarda: ZARAR                       {ours['ZARAR']:>3}")
    with_ours = ours["qoida bilan to'g'ri"]
    print(f"  Mazmun aniqligi: hozir {now_right}/{n} -> shakl bo'yicha {with_ours}/{n}")

    print("\n  Boshqarma (LOO javoblari):")
    for (label, outcome), value in sorted(boshqarma.items()):
        print(f"    {label:<30} {outcome:<10} {value:>3}")
    print("\n  Indeks (raqam boshidagi son) -> json'dagi boshqarma guruhi:")
    for index, groups in sorted(index_groups.items(), key=lambda kv: (len(kv[0]), kv[0])):
        print(f"    {index:>4}: " + ", ".join(f"{g} {c}" for g, c in groups.most_common()))


if __name__ == "__main__":
    main()
