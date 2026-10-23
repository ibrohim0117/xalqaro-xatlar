"""B7.4: papka rejimi uchun dev va test xatlarini alohida papkalarga ajratish.

data/real ni to'g'ridan-to'g'ri tanlasa, sahifaga 30 ta test xati ham kirib ketadi (ular faqat
yakuniy o'lchov uchun). Shuning uchun outputs/papkalar/{dev,test}/DOC_xxx/ yasaladi — har xatning
PDF va json'i. Nusxa emas, hardlink: fayl diskda ikki marta saqlanmaydi (maxfiy ma'lumot nusxasi
ko'paymaydi). outputs/ gitignore'da. Ekranga faqat sonlar chiqadi.

Ishga tushirish: poetry run python -m scripts.data.make_folders
"""

import os
import shutil
from pathlib import Path

from src.evaluation.dataset import list_letters, load_split

OUT_DIR = Path("outputs/papkalar")


def link(source: Path, target: Path) -> None:
    """Hardlink; boshqa diskda bo'lsa (hardlink mumkin emas) — nusxa."""
    target.unlink(missing_ok=True)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    split = load_split()
    for part in ("dev", "test"):
        for doc_id in split[part]:
            letter = letters[doc_id]
            folder = OUT_DIR / part / doc_id
            folder.mkdir(parents=True, exist_ok=True)
            link(letter.pdf, folder / letter.pdf.name)
            link(letter.truth, folder / letter.truth.name)
        print(f"{OUT_DIR / part}/: {len(split[part])} ta xat (PDF + json)")
    print("Sahifadagi 'Papka' tabida dev papkasini tanlang.")
    print("Test papkasi — faqat yakuniy o'lchov uchun (B6).")


if __name__ == "__main__":
    main()
