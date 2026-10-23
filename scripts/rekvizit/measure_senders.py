"""B5.1a: jo'natuvchi tashkilotlar qanday taqsimlangan (dev). Ekranga FAQAT sonlar chiqadi.

Asosiy savol: yangi xatning jo'natuvchisi oldin ko'rilgan bo'ladimi? Test javoblariga qaramaslik
uchun dev ichida taqlid qilinadi (leave-one-out): har xat uchun — uning jo'natuvchisi qolgan
dev xatlarining birortasida bormi?

Ishga tushirish: poetry run python -m scripts.rekvizit.measure_senders
"""

import re
import statistics
from collections import Counter

from src.common.text import normalize
from src.evaluation.dataset import list_letters, load_split, load_truth

CYRILLIC = re.compile(r"[А-Яа-яЁё]")


def sender_of(truth: dict) -> str:
    return (truth.get("rekvizit_document") or {}).get("hujjat_junatuvchi_tashkilot") or ""


def size_group(n: int) -> str:
    """Tashkilot nechta xat yuborgan — guruh nomi."""
    if n == 1:
        return "1 ta xat"
    if n <= 3:
        return "2–3 ta xat"
    if n <= 9:
        return "4–9 ta xat"
    return "10+ xat"


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    senders = [sender_of(load_truth(letters[doc_id])) for doc_id in load_split()["dev"]]
    keys = [normalize(s) for s in senders]
    per_sender = Counter(keys)
    n = len(keys)

    print(f"B5.1a: jo'natuvchi tashkilotlar, dev {n} xat\n")
    print(f"  turli tashkilotlar: {len(per_sender)}")
    print(f"  eng ko'p xat yuborgan tashkilot: {per_sender.most_common(1)[0][1]} ta xat")
    print(
        "\n  tashkilotlar necha xat yuborganiga ko'ra (tashkilotlar soni | ulardagi xatlar soni):"
    )
    groups = Counter()
    for count in per_sender.values():
        groups[(size_group(count), "tashkilot")] += 1
        groups[(size_group(count), "xat")] += count
    for label in ("1 ta xat", "2–3 ta xat", "4–9 ta xat", "10+ xat"):
        orgs, mails = groups[(label, "tashkilot")], groups[(label, "xat")]
        print(f"    {label:<11} {orgs:>3} tashkilot | {mails:>3} xat ({mails / n:4.0%})")

    seen = sum(per_sender[k] > 1 for k in keys)
    print("\n  Leave-one-out: xatning jo'natuvchisi boshqa dev xatlarida ham bormi?")
    print(f"    ha (tanish jo'natuvchi):     {seen:>3} ({seen / n:4.0%})")
    print(f"    yo'q (notanish jo'natuvchi): {n - seen:>3} ({(n - seen) / n:4.0%})")

    words = [len(s.split()) for s in senders]
    latin_only = sum(not CYRILLIC.search(s) for s in senders)
    print("\n  Nomlarning o'zi (json'da):")
    print(
        f"    so'zlar soni: median {statistics.median(words):g}, min {min(words)}, max {max(words)}"
    )
    print(f"    faqat lotin yozuvida: {latin_only}/{n}")


if __name__ == "__main__":
    main()
