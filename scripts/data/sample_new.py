"""Yangi to'plam (data/real2, 150 xat) dan tasodifiy N ta xat — papka rejimida sinash uchun.

Xatlar seed bilan bir marta aralashtiriladi; N ta — shu tartibning boshidagilari. Shuning uchun
keyin kattaroq N olinsa, avvalgi xatlar ham ichida bo'ladi, qolganlari esa hali ishlatilmagan —
keyingi o'lchov uchun yopiq. Tartib (faqat DOC raqamlari) outputs/papkalar/real2_tartib.json ga
yoziladi. Fayllar hardlink (nusxa emas), outputs/ gitignore'da. Ekranga faqat sonlar chiqadi.

Ishga tushirish:
    poetry run python -m scripts.data.sample_new --n 25              # boshidagi 25 ta
    poetry run python -m scripts.data.sample_new --skip 25 --n 125   # qolgan 125 ta (yakuniy)
"""

import argparse
import json
import random
from pathlib import Path

from scripts.data.make_folders import OUT_DIR, link
from src.evaluation.dataset import list_letters

NEW_DIR = Path("data/real2")
SEED = 2026
ORDER_FILE = OUT_DIR / "real2_tartib.json"


def new_root() -> Path:
    """Arxiv ichidagi yagona papka bo'lsa — o'sha (nomi ekranga chiqmaydi), aks holda data/real2."""
    inner = [p for p in NEW_DIR.iterdir() if p.is_dir()]
    return inner[0] if len(inner) == 1 else NEW_DIR


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=25, help="nechta xat")
    parser.add_argument("--skip", type=int, default=0, help="tartib boshidan nechtasini o'tkazish")
    args = parser.parse_args()
    letters = {letter.doc_id: letter for letter in list_letters(new_root())}
    order = sorted(letters)
    random.Random(SEED).shuffle(order)
    chosen = order[args.skip : args.skip + args.n]
    out = OUT_DIR / (f"real2_{args.n}" if not args.skip else f"real2_qolgan{len(chosen)}")
    for doc_id in chosen:
        letter = letters[doc_id]
        folder = out / doc_id
        folder.mkdir(parents=True, exist_ok=True)
        link(letter.pdf, folder / letter.pdf.name)
        link(letter.truth, folder / letter.truth.name)
    ORDER_FILE.parent.mkdir(parents=True, exist_ok=True)
    ORDER_FILE.write_text(json.dumps({"seed": SEED, "tartib": order}, indent=1), encoding="utf-8")
    print(f"{out}/: {len(chosen)} ta xat ({len(order)} tadan, seed {SEED}, {args.skip}-dan)")
    unused = len(order) - args.skip - len(chosen)
    print(f"Tartibda keyin yana {unused} ta xat qoldi.")


if __name__ == "__main__":
    main()
