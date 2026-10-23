"""B5.2a: imzo xatning qayerida va qanday ko'rinishda? O'girishimiz xodimnikiga mosmi? (dev)

json'dagi familiya ma'lum: matndagi har bir so'z lotinga o'girilib, familiyaga solishtiriladi
(o'xshashlik >= 85). Oxirgi mos kelgan joy — imzo joyi deb olinadi (imzo xat oxirida bo'ladi).
Ekranga FAQAT sonlar, turlar va harf bo'laklari ("shch→sh") chiqadi — ismlar chiqmaydi.

Ishga tushirish: poetry run python -m scripts.rekvizit.measure_signers
"""

import re
import statistics
from collections import Counter
from difflib import SequenceMatcher

from rapidfuzz import fuzz

from src.common.text import to_latin
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.signer import parse_json_signer
from src.reading.pdf_text import Word

CYR_WORD = re.compile(r"[А-ЯЁЎҚҒҲ][а-яёўқғҳ]{2,}(?:-[А-ЯЁ][а-яё]+)?")
LAT_WORD = re.compile(r"[A-Z][a-z]{2,}(?:-[A-Z][a-z]+)?")
INITIALS = re.compile(r"^(?:[А-ЯЁЎҚҒҲA-Z][а-яa-z]?\.){1,3}$")  # "А.", "А.Б.", "Ш.А."
TITLE = re.compile(
    r"начальник|заместител|директор|руководител|министр|председател|консул|исполняющ|"
    r"врио|глава|управляющ|секретар|boshliq|rahbar",
    re.IGNORECASE,
)
EDGE = re.compile(r"^[^\wЁё]+|[^\wЁё]+$")  # so'z boshi va oxiridagi tinish belgilari

# Hisoblagich kalitlari
FOUND, NOT_FOUND, BAD_SHAPE = "familiya topildi", "familiya matnda topilmadi", "json shakli boshqa"
EXACT, RIGHT, NEAR_TITLE = "o'girish aynan mos", "o'ng yarmida", "lavozim so'zi oldida"


def latin_of(token: str) -> str | None:
    """Kirill so'z — lotinga o'girilgan holi; lotin so'z — o'zi; boshqasi — None."""
    if CYR_WORD.fullmatch(token):
        return to_latin(token)
    if LAT_WORD.fullmatch(token):
        return token
    return None


def pattern(words: list[Word], i: int) -> str:
    """Imzo atrofidagi ko'rinish: bosh harflar oldindami, keyindami yoki ism to'liq yozilganmi."""
    prev = words[i - 1].text if i > 0 else ""
    nxt = words[i + 1].text if i + 1 < len(words) else ""
    if INITIALS.match(prev.strip(",")):
        return "И.О. Фамилия"
    if INITIALS.match(nxt.strip(",")):
        return "Фамилия И.О."
    if CYR_WORD.fullmatch(EDGE.sub("", prev)):
        return "Имя Фамилия"
    return "boshqa"


def translit_diffs(ours: str, theirs: str) -> list[str]:
    """Bizning o'girish va json o'rtasidagi farqli bo'laklar: ["shch→sh", "e→ye"]."""
    a, b = ours.lower(), theirs.lower()
    return [
        f"{a[i1:i2] or '∅'}→{b[j1:j2] or '∅'}"
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b).get_opcodes()
        if tag != "equal"
    ]


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = load_split()["dev"]
    stats, diffs, ys = Counter(), Counter(), []
    for doc_id in dev:
        doc = load_truth(letters[doc_id]).get("rekvizit_document") or {}
        parsed = parse_json_signer(doc.get("imzolagan_shaxs"))
        if parsed is None:
            stats[BAD_SHAPE] += 1
            continue
        initials, surname = parsed
        stats[f"{len(initials)} ta bosh harf"] += 1
        hits = []
        for page in get_pages(letters[doc_id]):
            words = page.main.words
            for i, word in enumerate(words):
                latin = latin_of(EDGE.sub("", word.text))
                if latin and fuzz.ratio(latin.lower(), surname.lower()) >= 85:
                    hits.append((page.number, words, i, latin))
        if not hits:
            stats[NOT_FOUND] += 1
            continue
        stats[FOUND] += 1
        stats[f"{min(len(hits), 3)}{'+' if len(hits) >= 3 else ''} marta"] += 1
        number, words, i, latin = hits[-1]
        stats[f"sahifa {number if number <= 2 else '3+'}"] += 1
        ys.append(words[i].y0)
        stats[RIGHT] += words[i].x0 >= 0.5
        stats[pattern(words, i)] += 1
        stats[NEAR_TITLE] += bool(TITLE.search(" ".join(w.text for w in words[max(0, i - 8) : i])))
        if latin.lower() == surname.lower():
            stats[EXACT] += 1
        diffs.update(translit_diffs(latin, surname))

    n, found = len(dev), stats[FOUND]
    print(f"B5.2a: imzolagan shaxs, dev {n} xat\n")
    print("  json'dagi shakl:")
    for key in ("1 ta bosh harf", "2 ta bosh harf", "3 ta bosh harf", BAD_SHAPE):
        print(f"    {key:<28} {stats[key]}")
    print(f"\n  familiya matnda topildi: {found}/{n} (topilmadi: {stats[NOT_FOUND]})")
    if not found:
        return
    print(f"  o'girishimiz json bilan aynan mos: {stats[EXACT]}/{found}")
    print("\n  imzo joyi (familiya oxirgi uchragan joy):")
    for key in ("sahifa 1", "sahifa 2", "sahifa 3+"):
        print(f"    {key:<28} {stats[key]}")
    print(f"    {'y median (0 tepa, 1 past)':<28} {statistics.median(ys):.2f}")
    print(f"    {RIGHT:<28} {stats[RIGHT]}")
    print(f"    {NEAR_TITLE + ' (8 so`z)':<28} {stats[NEAR_TITLE]}")
    print("  ko'rinishi:")
    for key in ("И.О. Фамилия", "Фамилия И.О.", "Имя Фамилия", "boshqa"):
        print(f"    {key:<28} {stats[key]}")
    print("  familiya xatda necha marta uchraydi:")
    for key in ("1 marta", "2 marta", "3+ marta"):
        print(f"    {key:<28} {stats[key]}")
    if diffs:
        print("  o'girish farqlari (bizniki → json, eng ko'p 10 tasi):")
        for chunk, count in diffs.most_common(10):
            print(f"    {chunk:<28} {count}")


if __name__ == "__main__":
    main()
