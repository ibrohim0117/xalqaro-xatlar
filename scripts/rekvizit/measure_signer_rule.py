"""B5.2b: imzoni javobsiz topish qoidasi — dev'da 4 variant. Ekranga FAQAT sonlar chiqadi.

Qoida: "И.О. Фамилия" shaklidagi nomzodlar, o'ng yarmidagilari, eng oxirgi sahifadagi eng
pastdagisi -> lotinga o'giriladi va json bilan solishtiriladi. Matn keshdan olinadi.

Ishga tushirish: poetry run python -m scripts.rekvizit.measure_signer_rule
"""

from src.common.text import normalize
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.layout import header_bottom
from src.fields.signer import candidates, choose_signer

VARIANTS = {
    "V1: 1–2-sahifa, o'ng yarmi": dict(max_pages=2, right_only=True),
    "V2: 1-sahifa, o'ng yarmi": dict(max_pages=1, right_only=True),
    "V3: 1–2-sahifa, hamma joy": dict(max_pages=2, right_only=False),
    "V4: hamma sahifa, o'ng yarmi": dict(max_pages=None, right_only=True),
    "V2a: V2 + pastki yarmi": dict(max_pages=1, right_only=True, min_y=0.5),
    "V2b: V2 + '№' qatoridan pastda": dict(max_pages=1, right_only=True, min_y="header"),
}


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = load_split()["dev"]
    data = []
    for doc_id in dev:
        truth = (load_truth(letters[doc_id]).get("rekvizit_document") or {}).get("imzolagan_shaxs")
        data.append((normalize(truth, spaceless=True), get_pages(letters[doc_id])))

    n = len(data)
    print(f"B5.2b: imzoni topish qoidasi, dev {n} xat")
    print("  yuqori chegara: 46 ta — imzo matnda o'qilgan xatlar (B5.2a)\n")
    print(f"  {'variant':<33}{'javob berdi':>14}{'to`g`ri':>12}{'ishonchlilik':>15}")
    for name, opts in VARIANTS.items():
        answered = correct = 0
        for truth, pages in data:
            min_y = opts.get("min_y", 0.0)
            if min_y == "header":
                min_y = header_bottom(pages[0])
            found = candidates(pages, opts["max_pages"])
            chosen = choose_signer(found, opts["right_only"], min_y)
            if chosen is None:
                continue
            answered += 1
            correct += normalize(chosen.latin(), spaceless=True) == truth
        reliability = f"{correct / answered:4.0%}" if answered else "   —"
        print(
            f"  {name:<33}{answered:>7} ({answered / n:4.0%}){correct:>5} ({correct / n:4.0%})"
            f"{reliability:>12}"
        )


if __name__ == "__main__":
    main()
