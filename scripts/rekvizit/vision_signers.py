"""B5.15: imzo — Apple Vision 1-sahifaning pastki yarmini o'qisa yordam beradimi (dev; test yopiq).

PDF matni buzilgan bo'lishi mumkin: birinchi bosh harf yo'qolgan (Candidate.damaged, ".К. Фамилия")
yoki imzo umuman topilmagan. Vision 1-sahifaning pastki yarmini (300 dpi) o'qiydi, so'zlar sahifa
koordinatalariga o'tkaziladi (vision.to_words) va o'sha imzo qoidasi (find_signer) qo'llanadi.
Prototip bilan bir xil kod: engine/signer_ocr (vision_signer, needs_vision); V2 = prototip.
Variantlar:
  V0 hozirgi (matn qatlami / sahifa OCR'i);
  V1 faqat Vision;
  V2 hozirgi, imzo topilmasa yoki buzilgan bo'lsa — Vision (Vision ham topmasa — hozirgisi).
To'g'ri — evaluate qoidasi bilan (json qiymati, bo'shliqsiz solishtirish).
Ekranga FAQAT sonlar va DOC raqamlari (ismlar emas).

Ishga tushirish: poetry run python -m scripts.rekvizit.vision_signers
"""

from collections import Counter, defaultdict

import pymupdf

from src.common.text import normalize
from src.engine.signer_ocr import DPI, VISION, needs_vision, vision_signer
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.signer import find_signer
from src.reading.engines import make_reader

VARIANTS = ("V0 hozirgi", "V1 faqat Vision", "V2 hozirgi, kerak bo'lsa Vision")
OUTCOMES = ("to'g'ri", "XATO", "yozilmadi")


def outcome(chosen, expected: str | None) -> str:
    if chosen is None:
        return "yozilmadi"
    ok = expected and normalize(chosen.latin(), spaceless=True) == normalize(expected, True)
    return "to'g'ri" if ok else "XATO"


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    reader = make_reader(VISION)
    counts, changes = Counter(), defaultdict(list)
    for number, doc_id in enumerate(dev, 1):
        print(f"\r  {number}/{len(dev)} xat…", end="", flush=True)
        letter = letters[doc_id]
        expected = (load_truth(letter).get("rekvizit_document") or {}).get("imzolagan_shaxs")
        current = find_signer(get_pages(letter))
        with pymupdf.open(letter.pdf) as doc:
            vision = vision_signer(doc[0], reader)
        use_vision = vision is not None and needs_vision(current)
        chosen_v2 = vision if use_vision else current
        picks = dict(zip(VARIANTS, (current, vision, chosen_v2), strict=True))
        base = outcome(current, expected)
        for variant, chosen in picks.items():
            result = outcome(chosen, expected)
            counts[variant, result] += 1
            if result != base:
                changes[variant, f"{base} -> {result}"].append(doc_id)

    print(f"\rImzo: Apple Vision sinovi, dev {len(dev)} xat (1-sahifa pastki yarmi, {DPI} dpi)\n")
    print(f"  {'':<34}" + "".join(f"{o:>11}" for o in OUTCOMES))
    for variant in VARIANTS:
        print(f"  {variant:<34}" + "".join(f"{counts[variant, o]:>11}" for o in OUTCOMES))
    print("\n  V0 dan farqi:")
    for (variant, change), docs in sorted(changes.items()):
        print(f"    {variant.split()[0]}: {change} ({len(docs)}): {', '.join(docs)}")


if __name__ == "__main__":
    main()
