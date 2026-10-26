"""Yangi xatlar: jo'natuvchi — xodim tasdig'isiz va tasdig'i bilan (amaldagi ishga yaqin baho).

Model eski 100 xatdan (outputs/model.json, build_model_all). Yangi xatlar DOC raqami tartibida
(kelish tartibi) o'tkaziladi; jo'natuvchini prototipning o'zi (engine.predict) yozadi yoki taklif
qiladi. Ikki variant:
  A — xotira o'zgarmaydi: papka rejimi natijasi bilan AYNAN bir xil bo'lishi kerak (tekshiruv);
  B — har xatdan keyin xodim to'g'ri nomni tasdiqlaydi va blank xotiraga qo'shiladi
      (feedback.with_confirmed — prototipdagi /confirm bilan bir xil yo'l).
Natija: to'g'ri yozildi / xato yozildi / yozilmadi — tashkilot xotirada bor yoki yo'q (birinchi
xati — muqarrar); bir bosishda (yozilgani to'g'ri yoki to'g'risi takliflarda).
Ekranga FAQAT sonlar chiqadi. Matn keshga tushadi (outputs/text_cache, gitignore).

Ishga tushirish: poetry run python -m scripts.rekvizit.simulate_new_feedback
"""

import argparse
from collections import Counter
from pathlib import Path

from scripts.rekvizit.measure_senders import sender_of
from src.common.text import normalize
from src.engine.feedback import with_confirmed
from src.engine.model import Model, load_model
from src.engine.predict import predict
from src.evaluation.dataset import list_letters, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.sender import SENDER_MODE, blank_words, header_text

FIELD = "hujjat_junatuvchi_tashkilot"
KINDS = ("to'g'ri", "xato", "yozilmadi: xotirada bor", "yozilmadi: yangi tashkilot")


def same(a: str | None, b: str | None) -> bool:
    return bool(a) and normalize(a) == normalize(b)


def simulate(data: list[tuple[str, list]], model: Model, learn: bool) -> Counter:
    """data: kelish tartibidagi (to'g'ri nom, sahifalar)."""
    counts = Counter()
    for truth, pages in data:
        answer = predict(pages, model)
        written = answer["rekvizit_document"][FIELD]
        options = answer["takliflar"].get(FIELD) or []
        if written:
            kind = "to'g'ri" if same(written, truth) else "xato"
        elif normalize(truth) in {normalize(n) for n in model.sender_names}:
            kind = "yozilmadi: xotirada bor"
        else:
            kind = "yozilmadi: yangi tashkilot"
        counts[kind] += 1
        counts["bir bosishda"] += same(written, truth) or any(same(o, truth) for o in options)
        if learn:  # xodim to'g'ri nomni tasdiqlaydi -> xotiraga
            model = with_confirmed(model, [blank_words(header_text(pages, SENDER_MODE))], [truth])
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", type=Path, default=Path("outputs/papkalar/real2_25"))
    args = parser.parse_args()
    letters = list_letters(args.folder)  # DOC raqami tartibida = kelish tartibi
    data = []
    for number, letter in enumerate(letters, 1):
        print(f"\r  {number}/{len(letters)} xat matni…", end="", flush=True)
        data.append((sender_of(load_truth(letter)), get_pages(letter)))
    model = load_model()
    n = len(data)
    print(f"\rJo'natuvchi, yangi xatlar ({n} ta, {args.folder.name}), model: eski 100 xat\n")
    print(f"  {'':<30}" + "".join(f"{k:>28}" for k in (*KINDS, "bir bosishda")))
    for label, learn in (("A tasdiqsiz (papka rejimi)", False), ("B xodim tasdiqlaydi", True)):
        c = simulate(data, model, learn)
        cells = "".join(f"{c[k]:>28}" for k in (*KINDS, "bir bosishda"))
        print(f"  {label:<30}{cells}")


if __name__ == "__main__":
    main()
