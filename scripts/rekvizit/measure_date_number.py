"""B5.3a: hujjat sanasi va raqamini matndan topish — dev. Ekranga FAQAT sonlar chiqadi.

1) Manbalar solishtiriladi: 1-sahifaning matn qatlami, OCR va ikkalasi birga.
2) Raqam xatolari va to'g'ri javoblari faqat shakli bilan (raqamlar 9 ga, harflar Я/A ga).
3) Yakuniy qoida (date_number_answer): sana — matn qatlamidan avtomatik, OCR'dan taklif;
   raqam — faqat taklif.
B3.3 dagi yuqori chegara: sana ~1/3, raqam ~1/4 xatda matnda bor. Matn keshdan olinadi.

Ishga tushirish: poetry run python -m scripts.rekvizit.measure_date_number
"""

from collections import Counter

from scripts.data.profile_data import shape
from src.common.text import normalize
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_number import date_and_number, date_number_answer, find_anchor

SOURCES = ("matn qatlami", "OCR", "OCR, keyin matn qatlami", "matn qatlami, keyin OCR")
MAIN_SOURCE = "matn qatlami, keyin OCR"


def answers(page1) -> dict[str, tuple[str | None, str | None]]:
    """Har manba uchun (sana, raqam)."""
    tl = date_and_number(page1.text_layer)
    ocr = date_and_number(page1.ocr) if page1.ocr else (None, None)
    return {
        "matn qatlami": tl,
        "OCR": ocr,
        "OCR, keyin matn qatlami": (ocr[0] or tl[0], ocr[1] or tl[1]),
        "matn qatlami, keyin OCR": (tl[0] or ocr[0], tl[1] or ocr[1]),
    }


def row(label: str, answered: int, correct: int, n: int) -> str:
    reliability = f"{correct / answered:4.0%}" if answered else "   —"
    return f"    {label:<34}{answered:>7}{correct:>6} ({correct / n:4.0%}){reliability:>11}"


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = load_split()["dev"]
    stats, wrong_shapes, right_shapes = Counter(), Counter(), Counter()
    for doc_id in dev:
        doc = load_truth(letters[doc_id]).get("rekvizit_document") or {}
        want = {
            "sana": normalize(doc.get("hujjat_sana"), True),
            "raqam": normalize(doc.get("hujjat_raqami"), True),
        }
        page1 = get_pages(letters[doc_id])[0]
        stats["langar: matn qatlami"] += find_anchor(page1.text_layer.words) is not None
        stats["langar: OCR"] += bool(page1.ocr) and find_anchor(page1.ocr.words) is not None

        for source, (date, number) in answers(page1).items():
            for field, got in (("sana", date), ("raqam", number)):
                if got:
                    ok = normalize(got, True) == want[field]
                    stats[(field, source, "javob")] += 1
                    stats[(field, source, "to'g'ri")] += ok
                    if field == "raqam" and source == MAIN_SOURCE:
                        (right_shapes if ok else wrong_shapes)[shape(got)] += 1

        auto_date, suggestions = date_number_answer(page1)
        policy = {
            "sana — avtomatik": auto_date,
            "sana — taklif": suggestions.get("hujjat_sana"),
            "raqam — taklif": suggestions.get("hujjat_raqami"),
        }
        for label, got in policy.items():
            if got:
                field = label.split()[0]
                stats[(label, "javob")] += 1
                stats[(label, "to'g'ri")] += normalize(got, True) == want[field]

    n = len(dev)
    print(f"B5.3a: sana va raqam matndan, dev {n} xat")
    tl, ocr = stats["langar: matn qatlami"], stats["langar: OCR"]
    print(f"  'sana № raqam' langari topildi: matn qatlami {tl}, OCR {ocr}\n")
    for field in ("sana", "raqam"):
        print(f"  {field.upper()} — manbalar:{'javob':>30}{'to`g`ri':>12}{'ishonchlilik':>15}")
        for source in SOURCES:
            stat = stats[(field, source, "javob")], stats[(field, source, "to'g'ri")]
            print(row(source, *stat, n))
        print()
    for title, shapes in (("to'g'ri", right_shapes), ("xato", wrong_shapes)):
        print(f"  RAQAM — {title} javoblar shakli ({MAIN_SOURCE}):")
        for kind, count in shapes.most_common():
            print(f"      {kind:<34} {count}")
    print(f"\n  YAKUNIY QOIDA:{'javob':>27}{'to`g`ri':>12}{'ishonchlilik':>15}")
    for label in ("sana — avtomatik", "sana — taklif", "raqam — taklif"):
        print(row(label, stats[(label, "javob")], stats[(label, "to'g'ri")], n))


if __name__ == "__main__":
    main()
