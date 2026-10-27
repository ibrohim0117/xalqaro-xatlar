"""Sana qanday tanlangani — berilgan xatlarda, qiymatsiz (27.10: Кызмат blanki, "✗ t✓" holatlar).

Ikki qism:
1. "№" nomzodlari: 1-sahifa yuqori yarmidagi "№" ga o'xshash hamma belgi (matn qatlami va OCR) —
   joyi, harfsiz tuzilmasi (mask: raqam 9, kirill К/к, lotin L/l), shu qatordagi oldingi va keyingi
   so'zlar shakli, holati (nomzod / "на" dan keyin / bank rekviziti) va qaysi biri tanlangani.
   Prototip qaysi langarni ishlatgani (ocr_regions) va qaysi bo'laklar kesilgani.
2. Sana tanlovi: prototip sana dvigateli (DateOcr) aynan o'zi ishlaydi. Har OCR va bo'lak o'qigan
   matndagi sana to'g'ri sanaga nisbatan; oyna va yil tuzatishdan keyingi nomzodlar; topuvchi va
   uning sanasi qaysi bo'lakdan; kim tasdiqlagani; yozilgan sana; to'g'ri sana takliflarda nechanchi
   o'rinda.
Ekranga sanalar, raqamlar va ismlar CHIQMAYDI — faqat munosabat ("to'g'ri", "yil farq", "boshqa
sana"), joy va harfsiz tuzilma.

Ishga tushirish (VLM yoqilgan bo'lsin — make vlm; bitta xat ~35 s):
    poetry run python -m scripts.ocr.explain_date_choice DOC_3181407 DOC_3181419 DOC_3181420
    ... --folder outputs/papkalar/real2_25   (standart papka)
"""

import argparse
from pathlib import Path

from scripts.ocr.explain_dates import relation
from scripts.prototype.measure_time import received_of
from scripts.rekvizit.explain_signers import mask
from src.engine.date_ocr import DateReading, build_date_ocr
from src.engine.locate import ocr_regions
from src.evaluation.dataset import list_letters, load_truth
from src.fields.date_number import (
    ANCHOR,
    ANCHOR_MAX_Y,
    SAME_LINE,
    after_na,
    anchor_of,
    find_anchor,
    is_account,
)
from src.fields.date_vote import FINDERS, engine_dates, first_date, windowed
from src.reading.pages import CachedPage, extract_pages, open_pdf
from src.reading.pdf_text import Word

DEFAULT_FOLDER = Path("outputs/papkalar/real2_25")
AROUND = 3  # "№" atrofida har tomondan nechta so'z ko'rsatiladi
CANDIDATE_KEYS = ("date", "line", "header_anchor", "header_first", "page")  # date_vote.engine_dates


def verdict(value: str | None, truth: str | None) -> str:
    """Bitta sana to'g'ri sanaga nisbatan, qiymatsiz: to'g'ri / kun, oy, yil farq / boshqa sana."""
    if not value:
        return "—"
    if not truth:
        return "json'da sana yo'q"
    if value == truth:
        return "to'g'ri"
    a, b = value.split("."), truth.split(".")
    if len(a) != 3 or len(b) != 3:
        return "boshqa sana"
    differ = [part for part, x, y in zip(("kun", "oy", "yil"), a, b, strict=True) if x != y]
    return f"{' va '.join(differ)} farq" if len(differ) < 3 else "boshqa sana"


def is_anchor_like(word: Word) -> bool:
    """ "№" ga o'xshash: langar qolipi (date_number.ANCHOR) yoki ichida "№" bor, yuqori yarmida."""
    return word.y0 < ANCHOR_MAX_Y and bool(ANCHOR.match(word.text) or "№" in word.text)


def neighbors(words: list[Word], i: int) -> tuple[str, str]:
    """Shu qatordagi (chapdan o'ngga) "№" dan oldingi va keyingi AROUND so'z — harfsiz."""
    line = sorted((w for w in words if abs(w.y0 - words[i].y0) <= SAME_LINE), key=lambda w: w.x0)
    pos = next(k for k, w in enumerate(line) if w is words[i])
    before = " ".join(mask(w.text) for w in line[max(0, pos - AROUND) : pos])
    after = " ".join(mask(w.text) for w in line[pos + 1 : pos + 1 + AROUND])
    return before or "—", after or "—"


def anchor_candidates(words: list[Word]) -> list[tuple[Word, str, str, str]]:
    """(so'z, holat, oldingi so'zlar, keyingi so'zlar) — yuqoridan pastga. Holat: "TANLANDI"
    (find_anchor shuni oladi), "nomzod", "на" dan keyin, bank rekviziti."""
    chosen = find_anchor(words)
    found = []
    for i, word in enumerate(words):
        if not is_anchor_like(word):
            continue
        if i == chosen:
            status = "TANLANDI"
        elif not ANCHOR.match(word.text):
            status = "«№» so'z ichida"
        elif after_na(words, i):
            status = '"на" dan keyin'
        elif is_account(words, i):
            status = "bank rekviziti"
        else:
            status = "nomzod (pastroqda)"
        found.append((word, status, *neighbors(words, i)))
    return sorted(found, key=lambda item: item[0].y0)


def print_anchors(first: CachedPage) -> None:
    print('  1) "№" nomzodlari (1-sahifa, yuqori yarmi):')
    for label, page in (("matn qatlami", first.text_layer), ("sahifa OCR", first.ocr)):
        if page is None:
            print(f"    {label}: yo'q")
            continue
        rows = anchor_candidates(page.words)
        print(f"    {label}: {len(rows)} ta")
        for word, status, before, after in rows:
            print(
                f"      y {word.y0:.2f} x {word.x0:.2f} '{mask(word.text)}' [{status}]"
                f"  oldin: '{before}'  keyin: '{after}'"
            )
    used = anchor_of(first)  # ocr_regions shu langardan kesadi: avval matn qatlami, keyin OCR
    if used is None:
        print("    prototip ishlatgan langar: yo'q (faqat header va butun sahifa kesiladi)")
    else:
        anchor = used[0]
        source = "matn qatlami" if any(w is anchor for w in first.text_layer.words) else "OCR"
        print(f"    prototip ishlatgan langar: {source}, y {anchor.y0:.2f} x {anchor.x0:.2f}")
    print(f"    kesilgan bo'laklar: {', '.join(ocr_regions(first))}")


def print_choice(reading: DateReading, truth: str | None, received) -> None:
    print(f"  2) Sana tanlovi (ishlagan OCR'lar: {', '.join(reading.readers) or 'yo`q'}):")
    if not truth:
        print("    json'da hujjat_sana yo'q — solishtirib bo'lmaydi")
        return
    print(f"    matn qatlamidan avtomatik: {verdict(reading.auto, truth)}")
    print("    o'qilgan matn (har bo'lak):")
    for reader in reading.readers:
        cells = [f"{crop}: {relation(text, truth)}" for crop, text in reading.texts[reader].items()]
        print(f"      {reader:<16} " + " | ".join(cells))
    found = [windowed(engine_dates(reading.texts[r]), received) for r in reading.readers]
    print("    nomzodlar (oyna va yil tuzatishdan keyin):")
    for reader, candidates in zip(reading.readers, found, strict=True):
        cells = [f"{key} {verdict(candidates[key], truth)}" for key in CANDIDATE_KEYS]
        print(f"      {reader:<16} " + " | ".join(cells))
    if reading.auto:
        print("    sana bosma — OCR faqat raqam uchun ishlagan")
    elif reading.readers and reading.readers[0] in FINDERS:
        finder, keys = reading.readers[0], FINDERS[reading.readers[0]]
        date = first_date(found, keys)
        key = next((k for k in keys if found[0][k]), "—")
        print(f"    topuvchi: {finder}, sanasi: {verdict(date, truth)} (bo'lak: {key})")
        confirmed = [
            f"{reader} ({', '.join(k for k, v in candidates.items() if v == date)})"
            for reader, candidates in zip(reading.readers[1:], found[1:], strict=True)
            if date and date in candidates.values()
        ]
        print(f"    tasdiqlaganlar: {', '.join(confirmed) or 'hech kim'}")
    else:
        print("    topuvchi yo'q (VLM ishlamadi) — date bo'laklarida kamida 2 OCR ovozi")
    print(f"    yozildi (tekshiring bilan): {verdict(reading.prefill, truth)}")
    tips = reading.suggestions
    place = next((k + 1 for k, tip in enumerate(tips) if tip == truth), None)
    where = f"{place}-o'rinda" if place else "yo'q"
    kinds = ", ".join(verdict(tip, truth) for tip in tips) or "—"
    print(f"    takliflar: {len(tips)} ta ({kinds}); to'g'ri sana: {where}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sana qanday tanlangani (qiymatsiz)")
    parser.add_argument("docs", nargs="+", help="DOC raqamlari")
    parser.add_argument("--folder", type=Path, default=DEFAULT_FOLDER)
    args = parser.parse_args()
    letters = {letter.doc_id: letter for letter in list_letters(args.folder)}
    engine = build_date_ocr()
    if engine is None:
        print("Sana OCR'lari yuklanmadi — faqat 1-qism ko'rsatiladi")
    for doc_id in args.docs:
        print(f"\n== {doc_id}")
        letter = letters.get(doc_id)
        if letter is None:
            print(f"  {args.folder} da topilmadi")
            continue
        doc = load_truth(letter)
        truth = (doc.get("rekvizit_document") or {}).get("hujjat_sana")
        pdf = letter.pdf.read_bytes()
        first = extract_pages(pdf, max_pages=1)[0]
        print_anchors(first)
        if engine is not None:
            with open_pdf(pdf) as opened:
                reading = engine.read(opened[0], first, received_of(doc))
            print_choice(reading, truth, received_of(doc))


if __name__ == "__main__":
    main()
