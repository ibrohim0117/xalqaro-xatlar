"""B2.2: "eng dangasa o'quvchi" — xatni o'qimaydi, har doim bir xil javob yozadi.

Faqat DEV kalitlaridan har maydon uchun eng ko'p uchragan qiymatni oladi va uni barcha xatlarga
(dev va test) yozadi. Bu pastki chegara: haqiqiy AI undan yaxshi bo'lishi shart.

Ekranga FAQAT sonlar chiqadi (qiymatlar emas). Natija outputs/baseline/ ga yoziladi (gitignore'da).

Ishga tushirish: poetry run python -m src.baseline
"""

import json
from collections import Counter
from pathlib import Path

from src.dataset import list_letters, load_split, load_truth
from src.evaluate import ALL_FIELDS, REKVIZIT_FIELDS, SPACELESS, normalize, true_values

OUT_DIR = Path("outputs/baseline")


def most_common(values: list[str | None], spaceless: bool = False) -> tuple[str | None, int]:
    """Eng ko'p uchragan qiymat va u necha marta uchragani.

    Tekislangan holda sanaladi: "O.N. Xrushev" va "O.N.Xrushev" bitta qiymat.
    """
    filled = [v for v in values if v]
    if not filled:
        return None, 0
    counts = Counter(normalize(v, spaceless) for v in filled)
    key, n = counts.most_common(1)[0]
    original = next(v for v in filled if normalize(v, spaceless) == key)
    return original, n


def learn(truths: list[dict[str, str | None]]) -> tuple[dict[str, str | None], dict[str, int]]:
    """Har maydon uchun yodlangan javob va u dev'da necha xatda uchragani."""
    guess, freq = {}, {}
    for field in ALL_FIELDS:
        values = [truth[field] for truth in truths]
        guess[field], freq[field] = most_common(values, spaceless=field in SPACELESS)
    return guess, freq


def to_prediction(values: dict[str, str | None]) -> dict:
    """Maydonlarni kalit json'i shakliga joylaydi — evaluate aynan shu shaklni o'qiydi."""
    boshqarma = values.get("boshqarma")
    return {
        "rekvizit_document": {field: values.get(field) for field in REKVIZIT_FIELDS},
        "tasks": [{"asosiy_ijrochilar_boshqarmalari": [boshqarma] if boshqarma else []}],
    }


def main() -> None:
    split = load_split()
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev_truths = [true_values(load_truth(letters[doc_id])) for doc_id in split["dev"]]
    guess, freq = learn(dev_truths)  # faqat dev — test kalitlariga qaralmaydi

    prediction = to_prediction(guess)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc_ids = split["dev"] + split["test"]
    for doc_id in doc_ids:
        text = json.dumps(prediction, ensure_ascii=False, indent=2)
        (OUT_DIR / f"{doc_id}.json").write_text(text, encoding="utf-8")

    print(f"Dangasa o'quvchi {len(dev_truths)} ta dev kalitidan yodladi:")
    for field in ALL_FIELDS:
        print(f"  {field:<28} eng ko'p uchragan javob {freq[field]:>2}/{len(dev_truths)} xatda")
    print(f"\n{len(doc_ids)} ta xatga (dev + test) bir xil javob yozildi: {OUT_DIR}/")
    print("Baholash: poetry run python -m src.evaluate outputs/baseline")


if __name__ == "__main__":
    main()
