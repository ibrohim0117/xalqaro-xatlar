"""Raqam (yangi 150 xat): to'g'ri raqam qayerda yo'qoladi — OCR uni umuman o'qiganmi, o'qigan
bo'lsa nega yozilmadi yoki takliflarga chiqmadi.

measure_time saqlagan OCR matnlaridan (simulate_arrival.saved_reading) prototip qoidasi
(number_ocr.read_number) qolipsiz qayta hisoblanadi: yangi xatlarda qolip natijani o'zgartirmadi
(simulate_arrival: qolipsiz = A = B). Nomzodlar — hamma OCR'larning hamma bo'laklaridan o'qilgan
raqamlar hamda matn qatlami va sahifa OCR'idagi "№" raqami.
Har xat bitta guruhga tushadi: ⚠ bilan to'g'ri yozildi; takliflarda 1/2/3-o'rinda; OCR o'qigan,
lekin takliflarda yo'q; hech qayerda yo'q — eng yaqin nomzod qanchalik farq qiladi (1 belgi,
2–3 belgi, qisman, boshqa raqam yoki hech narsa o'qilmagan).
Ustunlar: xato yozilgani, "№" langari topilgani (line bo'lagi o'qilgan), bosma raqam (matn
qatlamida "№" raqami bor). Kim o'qigan: to'g'ri raqamni har OCR nechta xatda topgan, yolg'iz
topgani alohida. Yaqin xatolar (1–3 belgi): tuzatish turlari.
Ekranga FAQAT sonlar; --ids — DOC raqami, guruh va xato shakli (raqam -> 9, harf -> A).

Ishga tushirish: poetry run python -m scripts.ocr.explain_numbers [--ids]
"""

import argparse
from collections import Counter, defaultdict

from rapidfuzz.distance import Levenshtein

from scripts.data.sample_new import new_root
from scripts.ocr.number_failures import edit_kinds, error_shape, relation
from scripts.rekvizit.simulate_arrival import saved_reading
from src.engine.number_ocr import read_number
from src.evaluation.dataset import list_letters, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_number import date_and_number
from src.fields.number_template import key
from src.fields.number_vote import engine_numbers
from src.reading.pages import CachedPage

WRITTEN = "⚠ bilan to'g'ri yozildi"
SUGGESTED = ("takliflarda 1-o'rinda", "takliflarda 2-o'rinda", "takliflarda 3-o'rinda")
READ = "OCR o'qigan, takliflarda yo'q"
NOTHING = "hech qayerda: hech narsa o'qilmagan"
NEAR = ("1 belgi farq", "2-3 belgi farq")
GROUPS = (
    WRITTEN,
    *SUGGESTED,
    READ,
    *(f"hech qayerda: {r}" for r in (*NEAR, "qisman", "boshqa raqam")),
    NOTHING,
)
COLUMNS = ("xato yozilgan", "langar bor", "bosma raqam bor")


def candidates(
    readers: list[str], texts: dict[str, dict[str, str]], first: CachedPage
) -> dict[str, set[tuple[str, str]]]:
    """Raqam nomzodlari (key ko'rinishida) -> kim o'qigan: {(OCR, bo'lak)}."""
    found: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for reader in readers:
        for crop, value in engine_numbers(texts.get(reader, {})).items():
            if value and key(value):
                found[key(value)].add((reader, crop))
    pages = {"matn qatlami": first.text_layer, "sahifa OCR": first.ocr}
    for source, page in pages.items():
        value = date_and_number(page)[1] if page is not None else None
        if value and key(value):
            found[key(value)].add(("matn", source))
    return found


def group_of(
    prefill: str | None, suggestions: list[str], found: dict, truth: str
) -> tuple[str, str | None]:
    """(guruh, eng yaqin nomzod — to'g'ri raqam hech qayerda bo'lmasa)."""
    right = key(truth)
    if prefill and key(prefill) == right:
        return WRITTEN, None
    ranks = [key(s) for s in suggestions]
    if right in ranks[: len(SUGGESTED)]:
        return SUGGESTED[ranks.index(right)], None
    if right in found:
        return READ, None
    if not found:
        return NOTHING, None
    nearest = min(sorted(found), key=lambda c: Levenshtein.distance(c, right))
    return f"hech qayerda: {relation(nearest, truth)}", nearest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", action="store_true", help="DOC raqami, guruh va xato shakli")
    args = parser.parse_args()
    letters = list_letters(new_root())
    rows = Counter()  # (guruh, ustun) -> soni
    by_reader, alone, by_crop = Counter(), Counter(), Counter()
    edits, ids, skipped, one_click = Counter(), [], 0, 0
    for number, letter in enumerate(letters, 1):
        print(f"\r  {number}/{len(letters)} xat…", end="", flush=True)
        truth = (load_truth(letter).get("rekvizit_document") or {}).get("hujjat_raqami")
        reading = saved_reading(letter.doc_id)
        if not truth or reading is None:
            skipped += 1
            continue
        first = get_pages(letter)[0]
        result = read_number(first, reading, None)
        found = candidates(reading.readers, reading.texts, first)
        group, nearest = group_of(result.prefill, result.suggestions, found, truth)
        rows[group, "xat"] += 1
        rows[group, "xato yozilgan"] += bool(result.prefill) and key(result.prefill) != key(truth)
        rows[group, "langar bor"] += any(
            "line" in reading.texts.get(r, {}) for r in reading.readers
        )
        rows[group, "bosma raqam bor"] += bool(date_and_number(first.text_layer)[1])
        one_click += group in (WRITTEN, *SUGGESTED)
        who = found.get(key(truth), set())
        readers = {reader for reader, _ in who}
        by_reader.update(readers)
        by_crop.update({crop for _, crop in who})
        if len(readers) == 1:
            alone.update(readers)
        if nearest and any(group.endswith(r) for r in NEAR):
            edits.update(edit_kinds(nearest, truth))
        if args.ids and group != WRITTEN:
            shape = f"; to'g'ri raqam shakli, xato joylari: {error_shape(nearest, truth)}"
            ids.append(f"{letter.doc_id}: {group}{shape if nearest else ''}")

    n = sum(rows[g, "xat"] for g in GROUPS)
    print("\r" + " " * 30 + "\r", end="")
    print(f"Raqam — yangi {n} xat, saqlangan OCR matnlari, prototip qoidasi (qolipsiz)")
    print(f"  (OCR matni yoki json'da raqam yo'q: {skipped} xat)\n")
    head = "to'g'ri raqam qayerda"
    print(f"  {head:<40}{'xat':>6}" + "".join(f"{c:>17}" for c in COLUMNS))
    for group in GROUPS:
        count = rows[group, "xat"]
        print(f"  {group:<40}{count:>6}" + "".join(f"{rows[group, c]:>17}" for c in COLUMNS))
    total = {c: sum(rows[g, c] for g in GROUPS) for c in COLUMNS}
    print(f"  {'jami':<40}{n:>6}" + "".join(f"{total[c]:>17}" for c in COLUMNS))
    print(f"\n  Bir bosishda (yozilgan yoki takliflarda): {one_click}/{n}")
    reached = sum(rows[g, "xat"] for g in (WRITTEN, *SUGGESTED, READ))
    print(f"  To'g'ri raqam biror OCR yoki matnda o'qilgan: {reached}/{n}")

    print("\n  To'g'ri raqamni kim o'qigan (xatlar soni; qavsda — faqat shu o'qigan):")
    for reader, count in by_reader.most_common():
        print(f"    {reader:<20}{count:>5} ({alone[reader]})")
    print("  Qaysi bo'lakda: " + ", ".join(f"{c} {k}" for c, k in by_crop.most_common()))
    print("\n  Yaqin xatolar (eng yaqin nomzod 1–3 belgi farq) — tuzatish turlari:")
    for kind, count in edits.most_common() or [("—", 0)]:
        print(f"    {kind:<30}{count:>5}")
    if args.ids:
        print("\n  Xatlar (to'g'ri yozilmaganlari):")
        for row in ids or ["—"]:
            print(f"    {row}")


if __name__ == "__main__":
    main()
