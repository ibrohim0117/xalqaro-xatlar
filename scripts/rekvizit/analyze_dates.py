"""Sana tahlili: 57 ta xatda sana nega topilmayapti — qoida, qo'lyozma yoki "№" yo'qligi.

Har dev xat uch holatdan biriga tushadi:
  A. sana avtomatik to'g'ri topildi (matn qatlamidan, hozirgi qoida);
  B. "№" langari bor, lekin sana topilmadi (yoki xato);
  C. "№" langari yo'q.
Har holatda: json'dagi to'g'ri sana 1-sahifa matnida (matn qatlami yoki OCR) BORMI — bor bo'lsa,
sana bosma va OCR uni o'qigan, demak qoidani tuzatish yetadi; yo'q bo'lsa — qo'lda yozilgan yoki
o'qilmagan.
Bor bo'lsa — qayerda: "№" qatorida, oldida "от" bilan (qoida tashlaydi), yoki boshqa joyda.
Keyin qoida nomzodlari (R0–R3) simulyatsiya qilinadi: har biri 70 xatda va sanasi topilmagan
xatlarda nechta to'g'ri, nechta xato sana beradi.
Ekranga FAQAT sonlar; --ids — qo'lda tekshirish uchun DOC raqamlari (qiymatlarsiz).

Ishga tushirish: poetry run python -m scripts.rekvizit.analyze_dates [--ids]
"""

import argparse
from collections import Counter, defaultdict

from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_number import (
    DATE_BAND,
    SAME_LINE,
    all_dates,
    date_and_number,
    find_anchor,
    parse_date,
)
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText

CASES = {
    "A": "avtomatik to'g'ri",
    "B": "'№' bor, sana topilmadi/xato",
    "C": "'№' yo'q",
}


def where_in(page: PageText, truth: str) -> str | None:
    """To'g'ri sana shu matnda qayerda: '№' qatorida / 'от' dan keyin / boshqa joyda.
    Yo'q bo'lsa — None."""
    found = [ot for date, ot in all_dates(page.text) if date == truth]
    if not found:
        return None
    i = find_anchor(page.words)
    if i is not None:
        a = page.words[i]
        band = " ".join(w.text for w in page.words if abs(w.y0 - a.y0) <= DATE_BAND)
        if any(date == truth for date, _ in all_dates(band)):
            return "'№' qatorida"
    return "'от' dan keyin" if all(found) else "boshqa joyda"


def classify(first: CachedPage, truth: str) -> tuple[str, str]:
    """(holat A/B/C, to'g'ri sana matnda qayerda — matn qatlami, keyin OCR)."""
    auto = date_and_number(first.text_layer)[0]
    has_anchor = find_anchor(first.text_layer.words) is not None or (
        first.ocr is not None and find_anchor(first.ocr.words) is not None
    )
    case = "A" if auto == truth else ("B" if has_anchor else "C")
    for source, page in (("matn qatlami", first.text_layer), ("OCR", first.ocr)):
        if page is not None and (place := where_in(page, truth)):
            return case, f"{source}: {place}"
    return case, "matnda yo'q (qo'lyozma / o'qilmagan)"


HEADER_MAX_Y = 0.35  # sarlavha (blank, "№" qatori) shu balandlikkacha
BOTTOM_MIN_Y = 0.65  # pastki qism (imzo atrofi)
RULES = [
    "R0 '№' qatori, 'от' bo'lsa ham",
    "R1 sarlavhadagi birinchi sana",
    "R2 pastki qismdagi oxirgi sana",
    "R3 sahifadagi yagona sana",
]


def dated_lines(page: PageText) -> list[tuple[float, list[tuple[str, bool]]]]:
    """Har qator: (y, [(sana, oldida "от")]) — faqat sanasi bor qatorlar, yuqoridan pastga."""
    lines: dict[int, list] = {}
    for word in page.words:
        lines.setdefault(word.line, []).append(word)
    found = []
    for words in lines.values():
        if dates := all_dates(" ".join(w.text for w in words)):
            found.append((min(w.y0 for w in words), dates))
    return sorted(found, key=lambda item: item[0])


def first_date(lines, low: float, high: float, last: bool = False) -> str | None:
    """Berilgan balandlikdagi qatorlardan birinchi (yoki oxirgi) sana; "от" dan keyingilari emas."""
    dates = [d for y, ds in lines if low <= y < high for d, ot in ds if not ot]
    return (dates[-1] if last else dates[0]) if dates else None


def rules(first: CachedPage) -> dict[str, str | None]:
    """Qoida nomzodlari: har biri bitta sana yoki None."""
    main = first.main
    lines = dated_lines(main)
    i = find_anchor(main.words)
    r0 = None
    if i is not None:  # "№ 123 от 12.03.2026" — "№" bilan AYNAN bir qatordagi sana, "от" bo'lsa ham
        a = main.words[i]
        same = sorted((w for w in main.words if abs(w.y0 - a.y0) <= SAME_LINE), key=lambda w: w.x0)
        r0 = parse_date(" ".join(w.text for w in same))
    unique = {d for _, ds in lines for d, ot in ds if not ot}
    values = [
        r0,
        first_date(lines, 0.0, HEADER_MAX_Y),
        first_date(lines, BOTTOM_MIN_Y, 1.01, last=True),
        unique.pop() if len(unique) == 1 else None,
    ]
    return dict(zip(RULES, values, strict=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", action="store_true", help="B va C holatlari DOC raqamlari")
    args = parser.parse_args()

    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    table: dict[str, Counter] = defaultdict(Counter)
    ids: dict[tuple[str, str], list[str]] = defaultdict(list)
    empty = 0
    rule_stats: Counter = Counter()
    for doc_id in dev:
        truth = (load_truth(letters[doc_id]).get("rekvizit_document") or {}).get("hujjat_sana")
        if not truth:
            empty += 1
            continue
        first = get_pages(letters[doc_id])[0]
        case, place = classify(first, truth)
        table[case][place] += 1
        ids[case, place].append(doc_id)
        for rule, value in rules(first).items():
            for scope in ("70 xat", "topilmagan") if case != "A" else ("70 xat",):
                if value:
                    rule_stats[rule, scope, "javob"] += 1
                    rule_stats[rule, scope, "to'g'ri"] += value == truth

    print(f"Sana tahlili, dev {len(dev)} xat (json'da sana bo'sh: {empty})")
    print("  to'g'ri sana 1-sahifa matnida qayerda (avval matn qatlami, keyin OCR)\n")
    for case, title in CASES.items():
        print(f"  {case}. {title}: {sum(table[case].values())}")
        for place, count in table[case].most_common():
            print(f"       {place:<45} {count:>3}")
            if args.ids and case != "A":
                print(f"         {', '.join(ids[case, place])}")
        print()

    n_missing = sum(sum(table[c].values()) for c in ("B", "C"))
    scopes = f"{'70 xatda':>22}{'topilmagan ' + str(n_missing):>22}"
    print(f"  Qoida nomzodlari (1-sahifa asosiy matni):{scopes}")
    print(f"  {'':<34}{'javob':>8}{'to`g`ri':>8}{'xato':>6}{'javob':>8}{'to`g`ri':>8}{'xato':>6}")
    for rule in RULES:
        row = f"  {rule:<34}"
        for scope in ("70 xat", "topilmagan"):
            answered, right = rule_stats[rule, scope, "javob"], rule_stats[rule, scope, "to'g'ri"]
            row += f"{answered:>8}{right:>8}{answered - right:>6}"
        print(row)


if __name__ == "__main__":
    main()
