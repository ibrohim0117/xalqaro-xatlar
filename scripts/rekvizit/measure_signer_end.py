"""Imzo — xat 2–4 sahifali bo'lsa: imzo xat matni TUGAGAN joyda (ilovalarda emas).

Hozirgi qoida faqat 1-sahifadan qidiradi. "1-sahifada yo'q bo'lsa 2–3-sahifadan" zaxirasi rad
etilgan edi (+1 to'g'ri, +3 xato): ilovalarda boshqa odamlar imzosi bor. Bu yerda boshqa g'oya:
xat oxiri xayrlashuv iborasidan ("С уважением", "З повагою", "Cu respect" …) topiladi va imzo
faqat shu iboradan PASTDA qidiriladi. Variantlar (1-sahifada imzo topilmagan xatlarda):
  E0 hozirgi (faqat 1-sahifa);
  E1 ibora turgan sahifada, iboradan pastda (o'ng yarmi);
  E2 E1, topilmasa — keyingi sahifaning yuqori yarmi (imzo yangi sahifaga o'tib ketgan);
  E3 2–4-sahifada imzo bloki: o'ng yarmidagi "И.О. Фамилия" bilan BIR QATORDA, chaproqda lavozim
     so'zi ("Начальник управления … А.Б. Сидоров") — birinchi shunday sahifa (ilovada kam).
1-o'lchov (26.10): xayrlashuv iborasi dev'da 7/70, yangi 25 da 2/25 xatda — E1/E2 hech narsa
o'zgartirmadi.
Hozirgi qoida topgan imzolar o'zgarmaydi. To'g'ri — evaluate qoidasi bilan (json, bo'shliqsiz).
Ekranga FAQAT sonlar va DOC raqamlari.

Ishga tushirish:
    poetry run python -m scripts.rekvizit.measure_signer_end                 # dev 70
    poetry run python -m scripts.rekvizit.measure_signer_end --folder outputs/papkalar/real2_25
"""

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

from src.common.text import normalize
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.signer import EDGE, TITLE, candidates, choose_signer, find_signer

END_PAGES = 4  # rahbar: xat 1–2-sahifada, aniqlik uchun 1–4; qolgani ilova
CLOSING = re.compile(r"^(?:уважением|повагою|respect|құрметпен|hormatlamak|урматлаш)$")
VARIANTS = ("E0 hozirgi", "E1 ibora sahifasi", "E2 E1 + keyingi sahifa", "E3 lavozim + imzo")
# lavozim: signer.TITLE (rus) + ukraincha "заступник", "голова"
TITLE_ANY = re.compile(rf"{TITLE.pattern}|заступник|голова")
OUTCOMES = ("to'g'ri", "XATO", "yozilmadi")


def closing_place(pages) -> tuple[int, float] | None:
    """Xayrlashuv iborasi (birinchisi, 1–4-sahifa): (sahifa indeksi, y)."""
    for index, page in enumerate(pages[:END_PAGES]):
        for word in page.main.words:
            if CLOSING.match(EDGE.sub("", word.text).lower()):
                return index, word.y0
    return None


def end_signer(pages, next_page: bool):
    """Ibora sahifasida iboradan pastda; next_page — topilmasa keyingi sahifaning yuqori yarmi."""
    place = closing_place(pages)
    if place is None:
        return None
    index, y = place
    found = choose_signer(candidates(pages[index : index + 1], None), min_y=y)
    if found is None and next_page and index + 1 < len(pages):
        upper = [c for c in candidates(pages[index + 1 : index + 2], None) if c.y0 < 0.5]
        found = choose_signer(upper)
    return found


def titled_signer(pages):
    """2–4-sahifa: o'ng yarmidagi nomzod, shu qatorda undan chapda lavozim so'zi bor."""
    for page in pages[1:END_PAGES]:
        words = page.main.words
        found = []
        for candidate in candidates([page], None):
            line = {w.line for w in words if (w.x0, w.y0) == (candidate.x0, candidate.y0)}
            left = [w for w in words if w.line in line and w.x1 <= candidate.box[0]]
            if any(TITLE_ANY.search(w.text.lower()) for w in left):
                found.append(candidate)
        if chosen := choose_signer(found):
            return chosen
    return None


def outcome(chosen, expected: str | None) -> str:
    if chosen is None:
        return "yozilmadi"
    ok = expected and normalize(chosen.latin(), spaceless=True) == normalize(expected, True)
    return "to'g'ri" if ok else "XATO"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, help="xatlar papkasi (berilmasa — dev 70)")
    args = parser.parse_args()
    if args.folder:
        letters = list_letters(args.folder)
    else:
        by_id = {letter.doc_id: letter for letter in list_letters()}
        letters = [by_id[d] for d in sorted(load_split()["dev"])]
    counts, changes, markers = Counter(), defaultdict(list), Counter()
    for number, letter in enumerate(letters, 1):
        print(f"\r  {number}/{len(letters)} xat…", end="", flush=True)
        expected = (load_truth(letter).get("rekvizit_document") or {}).get("imzolagan_shaxs")
        pages = get_pages(letter)
        current = find_signer(pages)
        place = closing_place(pages)
        markers["ibora bor" if place else "ibora yo'q"] += 1
        if place:
            markers[f"ibora {place[0] + 1}-sahifada"] += 1
        picks = {
            VARIANTS[0]: current,
            VARIANTS[1]: current or end_signer(pages, next_page=False),
            VARIANTS[2]: current or end_signer(pages, next_page=True),
            VARIANTS[3]: current or titled_signer(pages),
        }
        base = outcome(current, expected)
        for variant, chosen in picks.items():
            result = outcome(chosen, expected)
            counts[variant, result] += 1
            if result != base:
                changes[variant, f"{base} -> {result}"].append(letter.doc_id)

    label = args.folder.name if args.folder else "dev"
    print(f"\rImzo: xat oxiri (xayrlashuv iborasi) bo'yicha, {label} {len(letters)} xat\n")
    print("  ibora: " + ", ".join(f"{k} {v}" for k, v in sorted(markers.items())))
    print(f"\n  {'':<28}" + "".join(f"{o:>11}" for o in OUTCOMES))
    for variant in VARIANTS:
        print(f"  {variant:<28}" + "".join(f"{counts[variant, o]:>11}" for o in OUTCOMES))
    print("\n  E0 dan farqi:")
    for (variant, change), docs in sorted(changes.items()):
        print(f"    {variant.split()[0]}: {change} ({len(docs)}): {', '.join(docs)}")


if __name__ == "__main__":
    main()
