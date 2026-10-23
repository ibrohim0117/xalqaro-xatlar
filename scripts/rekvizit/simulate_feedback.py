"""B5.1c: qayta aloqa simulyatsiyasi — tizim bo'sh xotira bilan ishga tushadi, xatlar ketma-ket.

Har xat uchun: AI jo'natuvchini xotiradan qidiradi (o'xshashlik >= chegara bo'lsa — nom yozadi),
keyin "xodim" to'g'ri nomni (json'dagini) tasdiqlaydi va u xotiraga qo'shiladi.
Faraz: xatlar DOC raqami tartibida keladi; xodim xato qilmaydi.
Bir nechta variant (blank qismi, chegara) bir xil ma'lumotda solishtiriladi.
Ekranga FAQAT sonlar chiqadi. Matn keshdan olinadi.

Ishga tushirish: poetry run python -m scripts.rekvizit.simulate_feedback
"""

from collections import Counter

from scripts.rekvizit.measure_senders import sender_of
from src.common.text import normalize
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.sender import SENDER_MODE, SENDER_THRESHOLD, Matcher, blank_words, header_text

BUCKET = 10
KEYS = ["to'g'ri", "xato", "tekshirish (yangi tashkilot)", "tekshirish (tanilmadi)"]
VARIANTS = [  # (nomi, blank qismi, chegara)
    ("hozirgi: full, 0.7", SENDER_MODE, SENDER_THRESHOLD),
    ("A: left, 0.7", "left", 0.7),
    ("B: left, 0.6", "left", 0.6),
]


def simulate(data: list[tuple[str, list]], mode: str, threshold: float) -> list[Counter]:
    """data: kelish tartibidagi (to'g'ri nom, sahifalar). Har 10 xat uchun natijalar."""
    memory_texts: list[str] = []
    memory_names: list[str] = []
    seen: set[str] = set()  # xotirada bor tashkilotlar
    buckets: list[Counter] = []
    for i, (truth, pages) in enumerate(data):
        blank = header_text(pages, mode)
        name, score = (
            Matcher(memory_texts, memory_names).best(blank) if memory_texts else (None, 0.0)
        )
        if name is not None and score >= threshold:
            outcome = "to'g'ri" if normalize(name) == normalize(truth) else "xato"
        elif normalize(truth) in seen:
            outcome = "tekshirish (tanilmadi)"
        else:
            outcome = "tekshirish (yangi tashkilot)"
        if i % BUCKET == 0:
            buckets.append(Counter())
        buckets[-1][outcome] += 1
        # xodim to'g'ri nomni tasdiqlaydi -> xotiraga
        memory_texts.append(blank_words(blank))
        memory_names.append(truth)
        seen.add(normalize(truth))
    return buckets


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])  # kelish tartibi: DOC raqami bo'yicha
    data = [(sender_of(load_truth(letters[d])), get_pages(letters[d])) for d in dev]
    n = len(data)

    print(f"B5.1c: qayta aloqa simulyatsiyasi, dev {n} xat, bo'sh xotiradan boshlab")
    print("  xatlar DOC raqami tartibida; xodim xato qilmaydi\n")
    print(f"  {'variant':<22}" + "".join(f"{k:>30}" for k in KEYS))
    results = {}
    for name, mode, threshold in VARIANTS:
        buckets = simulate(data, mode, threshold)
        results[name] = buckets
        total = sum(buckets, Counter())
        print(f"  {name:<22}" + "".join(f"{total[k]:>30}" for k in KEYS))

    current = VARIANTS[0][0]
    print(f"\n  {current} — har 10 xat bo'yicha:")
    for b, counts in enumerate(results[current]):
        label = f"{b * BUCKET + 1}–{b * BUCKET + sum(counts.values())}"
        print(f"  {label:<22}" + "".join(f"{counts[k]:>30}" for k in KEYS))


if __name__ == "__main__":
    main()
