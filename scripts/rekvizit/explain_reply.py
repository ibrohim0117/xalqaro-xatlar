"""B5.6: javob xatlarda bizning xatimiz raqami matnda QAYERDA — qoidani to'g'ri qurish uchun.

json'dagi qolipdan ("<sana>-yildagi <raqam>-son xat ijrosi bo'yicha") raqam va sana olinadi;
1–6-sahifa matnidan aynan shu raqam qidiriladi va atrofi TAVSIFLANADI (matn ekranga chiqmaydi):
  - qaysi sahifada; oldida "№" bormi; yaqinida "от" va json sanasi bormi; oldin boshqa "№" bormi;
  - oldidagi 15 so'z ichida qaysi kalit so'zlar bor (ro'yxat oldindan berilgan — KEYWORDS);
  - bizning raqamlarimiz tuzilishi va to'liq shakli (9/9-9/9, 99/99-9/9999 — qiymat emas).
Shu tahlildan reply.our_reference qurildi (24.10: bizniki 11/11 tuzilishi 9/9-9/9, oldida "Ваш
запрос" emas — "Министерства юстиции Республики Узбекистан", 9 xatda oldin boshqa "№" bor).

Ishga tushirish: poetry run python -m scripts.rekvizit.explain_reply
"""

from collections import Counter

from src.common.text import most_common, normalize
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_number import all_dates
from src.fields.number_template import key, shape, structure
from src.fields.reply import parse_reply_summary

KEYWORDS = (
    "ваш",
    "запрос",
    "письм",
    "обращени",
    "поручени",
    "ходатайств",
    "исх",
    "в ответ",
    "министерств",
    "юстиции",
    "узбекистан",
    "сообща",
    "направля",
    "рассмотр",
    "исполнен",
)
BEFORE = 15  # so'z
NEAR = 12  # so'z


def occurrence(tokens: list[str], number_key: str) -> int | None:
    """Raqam boshlanadigan so'z (raqam bir necha so'zga bo'lingan bo'lishi mumkin) — birinchisi."""
    hits = [i for i in range(len(tokens)) if number_key in key("".join(tokens[i : i + 4]))]
    if not hits:
        return None
    i = hits[0]
    while i + 1 in hits:
        i += 1
    return i


def keywords_before(tokens: list[str], i: int) -> set[str]:
    context = " ".join(tokens[max(0, i - BEFORE) : i]).lower()
    return {word for word in KEYWORDS if word in context}


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    documents = {d: load_truth(letters[d]).get("rekvizit_document") or {} for d in dev}
    summaries = {d: doc.get("hujjatning_qisqacha_mazmuni") for d, doc in documents.items()}
    standard = most_common(list(summaries.values()))[0]
    where, words, shapes = Counter(), Counter(), Counter()
    replies = 0
    for doc_id in dev:
        reply = None
        if normalize(summaries[doc_id]) != normalize(standard):
            reply = parse_reply_summary(summaries[doc_id])
        if reply is None:
            continue
        replies += 1
        date, number = reply
        shapes[f"{structure(number)}  ({shape(number)})"] += 1
        for page_no, page in enumerate(get_pages(letters[doc_id])[:6], 1):
            tokens = page.main.text.split()
            i = occurrence(tokens, key(number))
            if i is None:
                continue
            where[f"sahifa {page_no}"] += 1
            just_before = tokens[max(0, i - 2) : i + 1]
            where["oldida '№' (2 so'z ichida)"] += any("№" in t for t in just_before)
            around = tokens[max(0, i - 6) : i + 7]
            where["'от' ±6 so'z ichida"] += any(t.lower() == "от" for t in around)
            near = " ".join(tokens[max(0, i - NEAR) : i + NEAR])
            where["json sanasi ±12 so'z ichida"] += date in {d for d, _ in all_dates(near)}
            where["json sanasi shu sahifada"] += date in {d for d, _ in all_dates(" ".join(tokens))}
            where["undan oldin boshqa '№' bor"] += any("№" in t for t in tokens[:i])
            words.update(keywords_before(tokens, i))
            break
        else:
            where["matnda topilmadi"] += 1

    print(f"B5.6: javob xatlarda bizning raqamimiz qayerda (dev, {replies} ta javob xat)\n")
    for label in sorted(where, key=lambda k: (not k.startswith("sahifa"), k)):
        print(f"  {label:<36} {where[label]:>3}")
    print(f"\n  Kalit so'zlar raqamdan oldingi {BEFORE} so'z ichida:")
    for word in KEYWORDS:
        if words[word]:
            print(f"    {word:<14} {words[word]:>3}")
    print("\n  Bizning raqamlar tuzilishi (to'liq shakli) — qiymat emas:")
    for label, count in shapes.most_common():
        print(f"    {label:<36} {count:>3}")


if __name__ == "__main__":
    main()
