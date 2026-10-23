"""B5.4: javob xatlar — "На № <raqam> от <sana>" qatori mazmun va boshqarmani yaxshilay oladimi.

Dev'da sanaladi:
1. json'dagi nostandart mazmunlardan nechtasi qolipda: "<sana>-yildagi <raqam>-son xat ijrosi
   bo'yicha";
2. "На №" qatori 1-sahifada bormi, to'lami, raqam/sana json'dagi mazmun bilan mosmi;
3. qoida "qator to'la (raqam va sana) bo'lsa — mazmun qolipda" qo'llansa, mazmun aniqligi qanday
   o'zgaradi (standart xatlarda yuzaga keladigan zarar ham hisobda);
4. javob xatlarda boshqarma (LOO javoblari, outputs/b4) va raqam boshidagi indeks -> boshqarma
   guruhi.
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
from src.fields.reply import reply_of, reply_summary

PRED_DIR = Path("outputs/b4")
TEMPLATE = re.compile(
    r"^(\d{1,2}\.\d{1,2}\.\d{4})\s*-?\s*y(?:il)?dagi\s+(.+?)\s*-?\s*son\s+xat\s+ijrosi\s+bo'yicha$"
)


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
    boshqarma = Counter()
    index_groups: dict[str, Counter] = defaultdict(Counter)
    for doc_id in dev:
        truth, summary = truths[doc_id], summary_of[doc_id]
        is_standard = normalize(summary) == normalize(standard)
        template = TEMPLATE.match(normalize(summary)) if not is_standard else None
        kind = "standart" if is_standard else ("qolip" if template else "boshqa nostandart")
        kinds[kind] += 1

        ref = reply_of(get_pages(letters[doc_id])[0])
        number, date = ref if ref else (None, None)
        line = (
            "yo'q" if ref is None else ("to'la (raqam o'qildi)" if number else "bo'sh / o'qilmadi")
        )
        lines[line] += 1

        if template:
            if ref is None or not number:
                in_template[f"qator {line}"] += 1
            else:
                in_template["raqam mos" if same(number, template[2]) else "raqam mos emas"] += 1
                in_template["sana ham mos" if same(date, template[1]) else "sana mos emas"] += 1
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
    print("\n  Boshqarma (LOO javoblari):")
    for (label, outcome), value in sorted(boshqarma.items()):
        print(f"    {label:<30} {outcome:<10} {value:>3}")
    print("\n  Indeks (raqam boshidagi son) -> json'dagi boshqarma guruhi:")
    for index, groups in sorted(index_groups.items(), key=lambda kv: (len(kv[0]), kv[0])):
        print(f"    {index:>4}: " + ", ".join(f"{g} {c}" for g, c in groups.most_common()))


if __name__ == "__main__":
    main()
