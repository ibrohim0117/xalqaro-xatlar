"""Sana-raqam langari ("№") — eski va yangi qoida: qaysi xatlarda o'zgardi va matndan olingan sana
va raqam to'g'riroq bo'ldimi.

Yangi qoida (date_number.find_anchor): "На ваш исх. №" / "на исх. №" (shu qatorda 3 so'z ichida
"на") va bank rekvizitlari ("б/с №", "ИНН", 10+ raqamli hisob) langar emas. Eski qoida — faqat
bevosita oldingi so'z "на". Langar sana/raqam bo'laklarini kesish joyini ham belgilaydi, shuning
uchun o'zgargan xatlarda OCR natijasi ham o'zgaradi — buni papka rejimi o'lchaydi; bu yerda matn
qatlami va sahifa OCR'idagi sana va raqam (OCR'siz, bir zumda).
Har o'zgargan xat: sana/raqam hukmi eski -> yangi, yangi langar joyi va qatori HARFSIZ
(mask: raqam 9, kirill К/к, lotin L/l — qiymat emas).
Ekranga FAQAT sonlar, tuzilmalar va DOC raqamlari.

Ishga tushirish:
    poetry run python -m scripts.rekvizit.measure_anchor                 # dev 70
    poetry run python -m scripts.rekvizit.measure_anchor --folder outputs/papkalar/real2_25
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from scripts.rekvizit.explain_signers import mask
from src.common.text import normalize
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields import date_number
from src.fields.date_number import (
    ANCHOR,
    ANCHOR_MAX_Y,
    DATE_BAND,
    SAME_LINE,
    TRAP_BEFORE,
    find_anchor,
    find_date,
    find_number,
)
from src.fields.date_vote import WINDOW_DAYS, in_window, to_day


def old_anchor(words) -> int | None:
    """Eski qoida (B5.3): faqat bevosita oldingi so'z "на" tekshiriladi."""
    found = [
        i
        for i, w in enumerate(words)
        if ANCHOR.match(w.text)
        and w.y0 < ANCHOR_MAX_Y
        and not (i > 0 and TRAP_BEFORE.match(words[i - 1].text.strip(".,")))
    ]
    return min(found, key=lambda i: words[i].y0, default=None)


def read(words, anchor) -> tuple[str | None, str | None]:
    if anchor is None:
        return None, None
    return find_date(words, anchor), find_number(words, anchor)


def _old_guard(low: str, start: int, end: int) -> bool:
    return False


def _guard_v1(low: str, start: int, end: int) -> bool:
    """1-himoya (birinchi urinish): oldida "№" yoki keyin "/raqam"."""
    after = low[end : end + 2]
    return low[max(0, start - 2) : start].strip().endswith("№") or (
        after[:1] == "/" and after[1:2].isdigit()
    )


def _date(words, anchor: int, left_only: bool) -> str | None:
    a = words[anchor]
    left = left_only and a.x0 < date_number.RECIPIENT_X
    for band in (SAME_LINE, DATE_BAND):
        near = (w for w in words if abs(w.y0 - a.y0) <= band)
        line = sorted(
            (w for w in near if not left or w.x0 < date_number.RECIPIENT_X), key=lambda w: w.x0
        )
        text = " ".join(w.text for w in line)
        if date := date_number.parse_date(text, skip_after_ot=True):
            return date
    return None


VARIANT_GUARDS = (  # (nomi, chap blok sharti, raqam ichi himoyasi)
    ("eski", False, _old_guard),
    ("chap", True, _old_guard),
    ("raqam-1", False, _guard_v1),
    ("raqam-2", False, date_number.inside_number),
    ("hozirgi", True, date_number.inside_number),
)


def auto_variants(words, anchor: int) -> dict[str, str | None]:
    """Bugungi himoyalarning har biri alohida: avtomatik sana qanday chiqadi."""
    out, saved = {}, date_number.inside_number
    try:
        for name, left, guard in VARIANT_GUARDS:
            date_number.inside_number = guard
            out[name] = _date(words, anchor, left)
    finally:
        date_number.inside_number = saved
    return out


def verdict(value: str | None, truth: str | None) -> str:
    if not value:
        return "yo'q"
    return "to'g'ri" if normalize(value, True) == normalize(truth, True) else "xato"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, help="xatlar papkasi (berilmasa — dev 70)")
    args = parser.parse_args()
    if args.folder:
        letters = list_letters(args.folder)
    else:
        by_id = {letter.doc_id: letter for letter in list_letters()}
        letters = [by_id[d] for d in sorted(load_split()["dev"])]
    changed, results, details = defaultdict(list), Counter(), []
    for letter in letters:
        truth = load_truth(letter).get("rekvizit_document") or {}
        first = get_pages(letter)[0]
        for source, page in (("matn qatlami", first.text_layer), ("sahifa OCR", first.ocr)):
            if page is None:
                continue
            words = page.words
            old, new = old_anchor(words), find_anchor(words)
            if old == new:
                continue
            changed[source].append(letter.doc_id)
            seen = {}
            for label, anchor in (("eski", old), ("yangi", new)):
                date, number = read(words, anchor)
                seen[label] = (
                    verdict(date, truth.get("hujjat_sana")),
                    verdict(number, truth.get("hujjat_raqami")),
                )
                results[source, label, "sana", seen[label][0]] += 1
                results[source, label, "raqam", seen[label][1]] += 1
            where = "—"
            if new is not None:
                a = words[new]
                same_line = (w for w in words if abs(w.y0 - a.y0) <= SAME_LINE)
                line = sorted(same_line, key=lambda w: w.x0)
                side = "o'ng" if a.x0 >= 0.5 else "chap"
                where = f"y {a.y0:.2f} {side}: '{' '.join(mask(w.text) for w in line[:10])}'"
            details.append(
                f"{letter.doc_id} [{source}] sana {seen['eski'][0]}->{seen['yangi'][0]}, "
                f"raqam {seen['eski'][1]}->{seen['yangi'][1]}; yangi langar {where}"
            )

    label = args.folder.name if args.folder else "dev"
    print(f"Langar ('№'): eski va yangi qoida, {label} {len(letters)} xat\n")
    for source in ("matn qatlami", "sahifa OCR"):
        docs = changed[source]
        print(f"  {source}: langar o'zgardi {len(docs)} xatda: {', '.join(docs) or '—'}")
        for field in ("sana", "raqam"):
            for version in ("eski", "yangi"):
                row = ", ".join(
                    f"{v} {results[source, version, field, v]}" for v in ("to'g'ri", "xato", "yo'q")
                )
                print(f"    {field:<6}{version:<6} {row}")
    print("\n  Matn qatlamidan sana (hozirgi kod, hamma xatlar; oynadagisi avtomatik yoziladi):")
    auto, wrong, variant_rows = Counter(), [], []
    for letter in letters:
        truth = load_truth(letter).get("rekvizit_document") or {}
        first = get_pages(letter)[0]
        received = to_day(truth.get("kirish_sana"))
        words = first.text_layer.words
        anchor = find_anchor(words)
        date = read(words, anchor)[0]
        if anchor is not None:
            variants = auto_variants(words, anchor)
            seen = {
                k: verdict(v, truth.get("hujjat_sana"))
                if in_window(v, received, WINDOW_DAYS)
                else "-"
                for k, v in variants.items()
            }
            if len(set(seen.values())) > 1:
                cells = ", ".join(f"{k} {v}" for k, v in seen.items())
                a = words[anchor]
                near = sorted(
                    (w for w in words if abs(w.y0 - a.y0) <= DATE_BAND), key=lambda w: w.x0
                )
                ctx = " ".join(f"{mask(w.text)}@{w.x0:.2f}" for w in near[:10])
                variant_rows.append(f"{letter.doc_id}: {cells}; langar x {a.x0:.2f}; {ctx}")
        if in_window(date, received, WINDOW_DAYS):
            result = verdict(date, truth.get("hujjat_sana"))
            auto[result] += 1
            if result == "xato":  # qayerdan olindi: langar qatori va sana joyi (harfsiz)
                a = words[anchor]
                band = sorted(
                    (w for w in words if abs(w.y0 - a.y0) <= DATE_BAND), key=lambda w: w.x0
                )
                side = "o'ng" if a.x0 >= 0.5 else "chap"
                masked = " ".join(mask(w.text) for w in band[:14])
                wrong.append(f"{letter.doc_id}: langar y {a.y0:.2f} {side}; atrofi '{masked}'")

    print("    " + ", ".join(f"{v} {auto[v]}" for v in ("to'g'ri", "xato")))
    for row in wrong:
        print(f"      XATO {row}")
    print("\n  Bugungi himoyalar alohida (avtomatik sana farq qilgan xatlar; '-' — yo'q):")
    print("    eski = bugungacha; chap = chap blok sharti; raqam-1/2 = raqam ichi himoyasi;")
    print("    hozirgi = chap + raqam-2")
    for row in variant_rows or ["—"]:
        print(f"    {row}")
    print("\n  Har xat:")
    for row in details:
        print(f"    {row}")


if __name__ == "__main__":
    main()
