"""Raqamdagi harflar: json'da qaysi alifboda yoziladi va OCR o'qigan kirill harflarni lotinga
o'girish raqamni to'g'rilaydimi (explain_numbers: 1 belgi farq qilgan 23 xatning 10 tasida
"harf o'rniga harf" — masalan json'da "I", OCR'da "И").

1) json'dagi raqamlar (eski 100 + yangi 150): harfi bor raqamlar alifbo bo'yicha va har harf
   necha raqamda uchragani (alohida harf — qiymat emas).
2) Prototip raqam qoidasi (number_vote.number_reading); OCR'lar va matn qatlami o'qigan hamma
   raqamlardagi harflar ovozdan OLDIN almashtiriladi (prototipda ham shu joyda bo'ladi):
     o'zgarishsiz;
     homoglif — ko'rinishi bir xil kirill harf lotinga (В -> B, Н -> H, С -> C);
     transliteratsiya — kirill harf lotin tovushiga (В -> V, Н -> N, И -> I);
     aralash — ko'rinishi bir xil bo'lsa homoglif, bo'lmasa transliteratsiya (В -> B, И -> I).
   dev 70 — compare_ocr matnlari, qolip bilan (o'zgarishsiz qatori number_failures NP bilan bir
   xil bo'lishi kerak: 23 to'g'ri, 6 xato); yangi 150 — measure_time matnlari, qolipsiz (yangi
   xatlarda qolip natijani o'zgartirmadi). "to'g'ri -> xato" va "-> to'g'ri" — o'zgarishsizga
   nisbatan (yozilgan qiymat).
Ekranga FAQAT sonlar, alohida harflar va (--ids) DOC raqamlari.

Ishga tushirish: poetry run python -m scripts.ocr.number_letters [--ids]
"""

import argparse
import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from scripts.data.sample_new import new_root
from scripts.ocr.compare_ocr import OUT_DIR
from scripts.ocr.fit_numbers import templates
from scripts.rekvizit.simulate_arrival import number_outcome, saved_reading
from src.common.text import CYR2LAT
from src.engine.date_ocr import DEFAULT_READERS, crops_for
from src.engine.number_ocr import NumberReading
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_number import date_and_number
from src.fields.number_template import Template
from src.fields.number_vote import engine_numbers, number_reading
from src.reading.pages import CachedPage

READERS = DEFAULT_READERS.split(",")
HOMOGLYPH = str.maketrans("АВЕКМНОРСТХУаеокрсху", "ABEKMHOPCTXYaeokpcxy")
CYRILLIC = set("абвгдеёжзийклмнопрстуфхцчшщъыьэюяўқғҳ")
KINDS = ("to'g'ri", "xato", "yozilmadi", "bir bosishda")


def homoglyph(value: str) -> str:
    return value.translate(HOMOGLYPH)


def transliterate(value: str) -> str:
    """Har kirill harf lotin tovushiga (katta-kichikligi saqlanadi; "Е" doim "E")."""
    out = []
    for ch in value:
        latin = CYR2LAT.get(ch.lower(), ch) if ch.lower() in CYRILLIC else ch
        out.append(latin.upper() if ch.isupper() else latin)
    return "".join(out)


MAPPINGS: dict[str, Callable[[str], str]] = {
    "o'zgarishsiz": lambda value: value,
    "homoglif": homoglyph,
    "transliteratsiya": transliterate,
    "aralash": lambda value: transliterate(homoglyph(value)),
}


def alphabet(number: str) -> str:
    """Raqamdagi harflar alifbosi: lotin / kirill / ikkalasi / harfsiz."""
    letters = [c.lower() for c in number if c.isalpha()]
    cyrillic = any(c in CYRILLIC for c in letters)
    latin = any("a" <= c <= "z" for c in letters)
    return {(True, True): "ikkalasi", (True, False): "kirill", (False, True): "lotin"}.get(
        (cyrillic, latin), "harfsiz"
    )


@dataclass
class Case:
    doc_id: str
    truth: str
    readers: list[str]
    found: list[dict[str, str | None]]  # har OCR: bo'lak -> raqam
    text: dict[str, str | None]  # matn qatlami va sahifa OCR'idagi "№" raqami
    template: Template | None


def text_numbers(first: CachedPage) -> dict[str, str | None]:
    """number_ocr.read_number bilan bir xil: matn qatlami va sahifa OCR'idagi raqam."""
    return {
        "matn qatlami": date_and_number(first.text_layer)[1],
        "sahifa OCR": date_and_number(first.ocr)[1] if first.ocr else None,
    }


def reading(case: Case, convert: Callable[[str], str]) -> NumberReading:
    """Prototip qoidasi — harflar almashtirilgan nomzodlar bilan."""

    def mapped(numbers: dict[str, str | None]) -> dict[str, str | None]:
        return {k: convert(v) if v else v for k, v in numbers.items()}

    found = [mapped(f) for f in case.found]
    return NumberReading(*number_reading(case.readers, found, mapped(case.text), case.template))


def dev_cases() -> list[Case]:
    """dev 70: compare_ocr matnlari, har OCR faqat prototip o'qiydigan bo'laklar (number_failures
    kabi), qolip — shu tashkilotning BOSHQA dev xatlaridan."""
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    saved = {r: json.loads((OUT_DIR / f"{r}.json").read_text(encoding="utf-8")) for r in READERS}
    truths = {d: load_truth(letters[d]).get("rekvizit_document") or {} for d in dev}
    learned = templates(truths)
    cases = []
    for doc_id in dev:
        truth = truths[doc_id].get("hujjat_raqami")
        if not truth:
            continue
        own = [
            {crop: t for crop, t in saved[r].get(doc_id, {}).items() if crop in crops_for(r)}
            for r in READERS
        ]
        first = get_pages(letters[doc_id])[0]
        found = [engine_numbers(texts) for texts in own]
        cases.append(Case(doc_id, truth, READERS, found, text_numbers(first), learned[doc_id]))
    return cases


def new_cases() -> list[Case]:
    """Yangi 150: measure_time saqlagan matnlar (faqat prototip o'qigan bo'laklar), qolipsiz."""
    cases = []
    for letter in list_letters(new_root()):
        truth = (load_truth(letter).get("rekvizit_document") or {}).get("hujjat_raqami")
        saved = saved_reading(letter.doc_id)
        if not truth or saved is None:
            continue
        first = get_pages(letter)[0]
        found = [engine_numbers(saved.texts[r]) for r in saved.readers]
        cases.append(Case(letter.doc_id, truth, saved.readers, found, text_numbers(first), None))
    return cases


def compare(label: str, cases: list[Case], ids: bool) -> None:
    counts, changed = Counter(), []
    base = {
        case.doc_id: number_outcome(reading(case, MAPPINGS["o'zgarishsiz"]), case.truth)
        for case in cases
    }
    for name, convert in MAPPINGS.items():
        for case in cases:
            kind, one_click = number_outcome(reading(case, convert), case.truth)
            counts[name, kind] += 1
            counts[name, "bir bosishda"] += one_click
            before = base[case.doc_id][0]
            if before == "to'g'ri" and kind != "to'g'ri":
                counts[name, "to'g'ri -> boshqa"] += 1
                changed.append(f"{name}: {case.doc_id} to'g'ri -> {kind}")
            if before != "to'g'ri" and kind == "to'g'ri":
                counts[name, "boshqa -> to'g'ri"] += 1
                changed.append(f"{name}: {case.doc_id} {before} -> to'g'ri")
    columns = (*KINDS, "to'g'ri -> boshqa", "boshqa -> to'g'ri")
    print(f"\n  {label} ({len(cases)} xat)")
    print(f"    {'':<20}" + "".join(f"{c:>19}" for c in columns))
    for name in MAPPINGS:
        print(f"    {name:<20}" + "".join(f"{counts[name, c]:>19}" for c in columns))
    if ids:
        for row in changed or ["o'zgargan xat yo'q"]:
            print(f"      {row}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", action="store_true", help="natijasi o'zgargan DOC raqamlari")
    args = parser.parse_args()
    numbers = [
        (load_truth(letter).get("rekvizit_document") or {}).get("hujjat_raqami")
        for root in (None, new_root())
        for letter in (list_letters() if root is None else list_letters(root))
    ]
    numbers = [n for n in numbers if n]
    kinds = Counter(alphabet(n) for n in numbers)
    letters = Counter(c.lower() for n in numbers for c in set(n) if c.isalpha())
    print(f"1) json'dagi raqamlar: {len(numbers)} ta (eski 100 + yangi 150)")
    print("   " + ", ".join(f"{k} {kinds[k]}" for k in ("harfsiz", "lotin", "kirill", "ikkalasi")))
    print("   harflar (nechta raqamda): " + ", ".join(f"{c} {k}" for c, k in letters.most_common()))
    print("\n2) Prototip raqam qoidasi — OCR o'qigan raqamlardagi harflar almashtirilsa:")
    compare(
        "dev 70, qolip bilan (o'zgarishsiz = number_failures NP: 23 to'g'ri, 6 xato)",
        dev_cases(),
        args.ids,
    )
    compare(
        "yangi 150, qolipsiz (o'zgarishsiz = explain_numbers: 65 to'g'ri, 14 xato)",
        new_cases(),
        args.ids,
    )


if __name__ == "__main__":
    main()
