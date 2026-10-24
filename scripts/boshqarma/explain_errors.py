"""B5.7: boshqarma — rasmiy LOO javoblaridagi (outputs/b4) har xato qaysi turdan.

Turlar (har tur boshqa yechim talab qiladi):
  - guruh xato: viloyat / notariat / xalqaro adashgan;
  - javob yo'q: hudud topilmadi (nomzod yo'q) yoki xalqaro (qoida bu guruhni bashorat qilmaydi);
  - hudud xato: to'g'ri hudud nomzodlar ichida BOR (tanlash xatosi) yoki YO'Q;
  - nom farq: hudud to'g'ri, lekin boshqarma nomi json'dagidan boshqacha (LOO: hudud dev'da
    yagona xatda bo'lsa, model nomini bilmaydi va shablon "<hudud> adliya boshqarmasi" yozadi).
Ekranga FAQAT sonlar, hudud kalitlari va DOC raqamlari chiqadi (nomlar emas).

Avval: poetry run python -m scripts.prototype.run_predict
Ishga tushirish: poetry run python -m scripts.boshqarma.explain_errors
"""

from collections import Counter, defaultdict
from pathlib import Path

from src.common.schema import expected_boshqarma, group_of
from src.common.text import normalize
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.evaluate import load_prediction, predicted_boshqarma
from src.evaluation.text_cache import get_pages
from src.fields.boshqarma import REGION_PAGES, letter_regions
from src.fields.regions import region_of_boshqarma

PRED_DIR = Path("outputs/b4")


def kind_of(expected: str | None, predicted: str | None, candidates: set[str]) -> str:
    """Xato turi (to'g'ri bo'lsa — "to'g'ri")."""
    if predicted and normalize(predicted) == normalize(expected):
        return "to'g'ri"
    want, got = group_of(expected), group_of(predicted) if predicted else None
    if not predicted:
        if want == "viloyat":
            return "javob yo'q: hudud topilmadi"
        return f"javob yo'q: {want}"
    if want != got:
        return f"guruh xato: {want} -> {got}"
    region, guess = region_of_boshqarma(expected), region_of_boshqarma(predicted)
    if region != guess:
        return "hudud xato: to'g'risi nomzodlarda bor" if region in candidates else "hudud xato"
    return "nom farq (hudud to'g'ri)"


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    truths = {d: load_truth(letters[d]) for d in dev}
    regions = Counter(region_of_boshqarma(expected_boshqarma(t)) for t in truths.values())
    kinds, docs = Counter(), defaultdict(list)
    for doc_id in dev:
        expected = expected_boshqarma(truths[doc_id])
        predicted = predicted_boshqarma(load_prediction(PRED_DIR, doc_id))
        pages = get_pages(letters[doc_id])
        candidates = {hit.key for hit in letter_regions(pages, max_pages=REGION_PAGES)}
        kind = kind_of(expected, predicted, candidates)
        if kind.startswith("nom farq"):
            once = regions[region_of_boshqarma(expected)] == 1
            kind += ", hudud dev'da yagona" if once else ", hudud dev'da 2+"
        kinds[kind] += 1
        if kind != "to'g'ri":
            docs[kind].append(doc_id)

    print(f"Boshqarma xatolari (LOO javoblari, dev {len(dev)} xat)\n")
    for kind, count in sorted(kinds.items(), key=lambda kv: (kv[0] != "to'g'ri", -kv[1])):
        print(f"  {kind:<52} {count:>3}")
    print("\n  DOC raqamlari:")
    for kind, ids in sorted(docs.items()):
        print(f"    {kind} ({len(ids)}): {', '.join(ids)}")


if __name__ == "__main__":
    main()
