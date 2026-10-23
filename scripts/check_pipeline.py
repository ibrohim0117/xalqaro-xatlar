"""B7.1: yangi zanjir (PDF baytlari -> 1–6-sahifa -> javob) real dev xatlarda.

Ikki narsa tekshiriladi:
1. vaqt — bitta xat necha soniyada qayta ishlanadi (OCR bilan, keshsiz);
2. moslik — javob B4–B5 o'lchovlaridagi zanjir (kesh, hamma sahifa) javobi bilan bir xilmi.
Ikkalasida bir xil model (outputs/model.json) ishlatiladi, qayta aloqa xotirasi qo'shilmaydi.
Ekranga FAQAT vaqt, sahifa soni va sonlar chiqadi — xat mazmuni chiqmaydi.

Ishga tushirish: poetry run python -m scripts.check_pipeline --limit 5
"""

import argparse
import statistics
import time

from src.dataset import list_letters, load_split
from src.pipeline import MAX_PAGES, process_pdf
from src.predict import load_model, predict
from src.text_cache import get_pages


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5, help="nechta dev xat")
    args = parser.parse_args()

    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])[: args.limit]
    model = load_model()
    times, same = [], 0
    print(f"B7.1: yangi zanjir, {len(dev)} ta dev xat (har biridan ko'pi {MAX_PAGES} sahifa)\n")
    for i, doc_id in enumerate(dev, 1):
        letter = letters[doc_id]
        start = time.perf_counter()
        answer, _ = process_pdf(letter.pdf.read_bytes(), model)
        seconds = time.perf_counter() - start
        cached = get_pages(letter)
        match = answer == predict(cached, model)
        times.append(seconds)
        same += match
        read = min(len(cached), MAX_PAGES)
        print(f"  {i:>2}. {seconds:5.1f} s | {read} / {len(cached)} sahifa | bir xil: {match}")
    print(f"\n  vaqt: median {statistics.median(times):.1f} s, eng ko'pi {max(times):.1f} s")
    print(f"  javob kesh zanjiri bilan bir xil: {same} / {len(dev)}")


if __name__ == "__main__":
    main()
