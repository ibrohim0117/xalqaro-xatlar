"""B7.1: yangi zanjir (PDF baytlari -> 1–6-sahifa -> javob) real dev xatlarda.

Ikki narsa tekshiriladi:
1. vaqt — bitta xat necha soniyada qayta ishlanadi (keshsiz), shundan OCR'ga qanchasi ketadi;
2. moslik — javob B4–B5 o'lchovlaridagi zanjir (kesh, hamma sahifa) javobi bilan bir xilmi.
Ikkalasida bir xil model (outputs/model.json) ishlatiladi, qayta aloqa xotirasi qo'shilmaydi.
Ekranga FAQAT vaqt, sahifa va OCR soni chiqadi — xat mazmuni chiqmaydi.

Ishga tushirish: poetry run python -m scripts.prototype.check_pipeline --limit 5
"""

import argparse
import statistics

from src.engine.model import load_model
from src.engine.pipeline import MAX_PAGES, process_pdf
from src.engine.predict import predict
from src.evaluation.dataset import list_letters, load_split
from src.evaluation.text_cache import get_pages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5, help="nechta dev xat")
    args = parser.parse_args()

    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])[: args.limit]
    model = load_model()
    times, ocr_times, same = [], [], 0
    print(f"B7.1: yangi zanjir, {len(dev)} ta dev xat (har biridan ko'pi {MAX_PAGES} sahifa)\n")
    for i, doc_id in enumerate(dev, 1):
        letter = letters[doc_id]
        result = process_pdf(letter.pdf.read_bytes(), model)
        cached = get_pages(letter)
        match = result.answer == predict(cached, model)
        times.append(result.seconds)
        ocr_times.append(result.ocr.seconds)
        same += match
        print(
            f"  {i:>2}. {result.seconds:5.1f} s (OCR {result.ocr.seconds:5.1f} s, "
            f"{result.ocr.calls} marta) | {result.pages} / {len(cached)} sahifa | bir xil: {match}"
        )
    print(f"\n  vaqt: median {statistics.median(times):.1f} s, eng ko'pi {max(times):.1f} s")
    ocr_total, total = sum(ocr_times), sum(times)
    print(f"  OCR ulushi: {ocr_total / total:.0%} (jami {ocr_total:.0f} / {total:.0f} s)")
    print(f"  javob kesh zanjiri bilan bir xil: {same} / {len(dev)}")


if __name__ == "__main__":
    main()
