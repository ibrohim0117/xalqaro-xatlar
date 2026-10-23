"""B4.4: modelni dev'dan o'rganadi va dev xatlar uchun AI javoblarini yozadi.

Ekranga FAQAT sonlar chiqadi (boshqarma nomlari emas). Javoblar outputs/b4/ ga, model
outputs/model.json ga yoziladi (gitignore'da). Matn keshdan olinadi (B3.4).

Ishga tushirish:
    poetry run python -m scripts.run_predict
    poetry run python -m src.evaluate outputs/b4      # rasmiy baholash (B2)
"""

import json
from collections import Counter
from pathlib import Path

from src.dataset import list_letters, load_split, load_truth
from src.predict import learn_model, predict, save_model, template_matches
from src.text_cache import get_pages

OUT_DIR = Path("outputs/b4")


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = load_split()["dev"]
    model = learn_model([load_truth(letters[doc_id]) for doc_id in dev])  # faqat dev
    save_model(model)
    same, total = template_matches(model)
    print(f"Model dev'dan o'rganildi: {len(model.names)} ta boshqarma nomi + qisqacha mazmun")
    print(f"  viloyat nomlaridan '<hudud> adliya boshqarmasi' shabloniga mos: {same}/{total}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    flags = Counter()
    for doc_id in dev:
        answer = predict(get_pages(letters[doc_id]), model)
        flags.update(answer["tekshirish_kerak"])
        text = json.dumps(answer, ensure_ascii=False, indent=2)
        (OUT_DIR / f"{doc_id}.json").write_text(text, encoding="utf-8")
    print(f"\n{len(dev)} ta dev xat uchun javob yozildi: {OUT_DIR}/")
    print(f"  'tekshirish kerak' belgisi: {dict(flags) or 'yo`q'}")
    print(f"Baholash: poetry run python -m src.evaluate {OUT_DIR}")


if __name__ == "__main__":
    main()
