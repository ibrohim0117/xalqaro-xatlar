"""B4.2 xatolarini ko'rib chiqish uchun: har xato xatdan manzilga oid bo'laklarni FAYLGA yozadi.

MAXFIYLIK: bo'laklar real xat matni — faqat outputs/b4_kontekst/ ga (gitignore'da), ekranga
faqat sonlar chiqadi. Fayllarni chatga nusxalamang.

Avval (outputs/b4_hudud_xatolar.csv ni yozadi):
    poetry run python -m scripts.boshqarma.measure_regions
Ishga tushirish: poetry run python -m scripts.boshqarma.region_context
"""

import csv
import re
from pathlib import Path

from src.evaluation.dataset import list_letters
from src.evaluation.text_cache import get_pages
from src.fields.boshqarma import letter_regions, recipient_and_body
from src.fields.regions import Hit, prepare

ERRORS_FILE = Path("outputs/b4_hudud_xatolar.csv")
OUT_DIR = Path("outputs/b4_kontekst")
CONTEXT = 120  # topilgan so'zdan oldin va keyin nechta belgi
# Manzil va joy atrofida uchraydigan so'zlar
CLUES = re.compile(
    r"узбек|ўзбек|o'zbek|обл\.|област|район|р-н|туман|загс|махалл|кишлак|қишлоқ|"
    r"прожива|адрес|уроженец|уроженк|родил|место рождения|ташкент|"
    r"тошкент|toshkent|viloyat|вилоят|tuman|туман|fhdyo|фҳдё|фхдё",
    re.IGNORECASE,
)


def page_texts(pages) -> list[tuple[int, str]]:
    """Har sahifa matni; 1-sahifada qabul qiluvchi bloki chiqarilgan (B4.2 dagidek)."""
    result = [(1, recipient_and_body(pages[:1])[1])] if pages else []
    return result + [(page.number, page.main.text) for page in pages[1:]]


def snippets(text: str) -> list[str]:
    """Kalit so'zlar atrofidagi bo'laklar; bir-biriga tegib turganlari birlashtiriladi."""
    spans: list[list[int]] = []
    for m in CLUES.finditer(text):
        start, end = max(0, m.start() - CONTEXT), min(len(text), m.end() + CONTEXT)
        if spans and start <= spans[-1][1]:
            spans[-1][1] = end
        else:
            spans.append([start, end])
    return [" ".join(text[s:e].split()) for s, e in spans]


def filtered_hits(pages) -> list[tuple[Hit, str]]:
    """Asosiy qoida (C) tashlab yuborgan topilmalar va sababi: o'ng blok yoki vazirlik manzili."""
    kept = set(letter_regions(pages))
    raw = letter_regions(pages, recipient_mode="keep", drop_ministry=False)
    body_start = len(prepare(recipient_and_body(pages)[0])) + 1  # letter_regions'dagi chegara
    return [
        (hit, "o'ng blok" if hit.start < body_start else "vazirlik manzili yonida")
        for hit in raw
        if hit not in kept
    ]


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    with ERRORS_FILE.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for i, row in enumerate(rows, 1):
        pages = get_pages(letters[row["doc_id"]])
        lines = [
            f"{i}) {row['doc_id']} | kutilgan: {row['kutilgan']} | topilgan: {row['topilgan']}",
            f"   kod topgani: {row['topilmalar'] or '(hech narsa)'}",
            "   filtr tashlab yuborgani: "
            + (
                "; ".join(
                    f"{h.key}:{h.weight}«{h.text}» ({why})" for h, why in filtered_hits(pages)
                )
                or "(hech narsa)"
            ),
            "",
        ]
        for number, text in page_texts(pages):
            for snippet in snippets(text):
                lines.append(f"[{number}-sahifa] ...{snippet}...\n")
                total += 1
        (OUT_DIR / f"{i:02d}_{row['doc_id']}.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(rows)} ta xat, {total} ta bo'lak yozildi: {OUT_DIR}/")
    print("  Fayllarni o'zingiz oching. Matnni chatga nusxalamang.")


if __name__ == "__main__":
    main()
