"""B4.4, B5.1: modelni dev'dan o'rganadi va dev xatlar uchun AI javoblarini yozadi.

Dev'ni baholashda har xat uchun model QOLGAN 69 xatdan quriladi (leave-one-out): aks holda xat
jo'natuvchisini "o'zidan" topib oladi, yagona xatli hududning nomini ham o'zidan o'rganadi.
outputs/model.json ga esa 70 ta dev xatning hammasidan qurilgan model yoziladi (prototip va test
uchun — test xatlari dev'da yo'q).

Ekranga FAQAT sonlar chiqadi. Javoblar outputs/b4/ ga yoziladi (gitignore'da).
Ishga tushirish:
    poetry run python -m scripts.prototype.run_predict
    poetry run python -m src.evaluation.evaluate outputs/b4      # rasmiy baholash (B2)
"""

import json
from collections import Counter
from pathlib import Path

from src.engine.model import learn_model, save_model, template_matches
from src.engine.predict import predict
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.sender import SENDER_MODE, header_text

OUT_DIR = Path("outputs/b4")


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = load_split()["dev"]
    pages = [get_pages(letters[doc_id]) for doc_id in dev]
    truths = [load_truth(letters[doc_id]) for doc_id in dev]
    blanks = [header_text(p, SENDER_MODE) for p in pages]  # jo'natuvchi blanki

    model = learn_model(truths, blanks)  # hamma 70 ta dev xatdan — prototip va test uchun
    save_model(model)
    same, total = template_matches(model)
    print(f"Model dev'dan o'rganildi: {len(model.names)} ta boshqarma nomi, qisqacha mazmun,")
    print(f"  {len(model.sender_names)} ta xatdan jo'natuvchi namunalari")
    print(f"  viloyat nomlaridan '<hudud> adliya boshqarmasi' shabloniga mos: {same}/{total}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    flags = Counter()
    for i, doc_id in enumerate(dev):
        rest = [j for j in range(len(dev)) if j != i]  # leave-one-out: xatning o'zisiz
        model_i = learn_model([truths[j] for j in rest], [blanks[j] for j in rest])
        answer = predict(pages[i], model_i)
        flags.update(answer["tekshirish_kerak"])
        text = json.dumps(answer, ensure_ascii=False, indent=2)
        (OUT_DIR / f"{doc_id}.json").write_text(text, encoding="utf-8")
    print(f"\n{len(dev)} ta dev xat uchun javob yozildi (leave-one-out): {OUT_DIR}/")
    print(f"  'tekshirish kerak' belgilari: {dict(flags) or 'yo`q'}")
    print(f"Baholash: poetry run python -m src.evaluation.evaluate {OUT_DIR}")


if __name__ == "__main__":
    main()
