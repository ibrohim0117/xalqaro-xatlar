"""B5.8: jo'natuvchi — rasmiy LOO (run_predict bilan aynan bir xil) javobsiz va xato xatlar turi.

Har dev xati uchun model qolgan 69 xatdan quriladi (learn_model; xodim tasdiqlari ishlatilmaydi),
blank eng o'xshash dev blanki bilan solishtiriladi (Matcher, SENDER_THRESHOLD). Turlar:
  - yozildi to'g'ri / yozildi xato;
  - tanish (tashkilotning boshqa dev xati bor), ball past: eng o'xshashi to'g'ri yoki xato — chegara
    muammosi; ball va 2-o'rindagi BOSHQA tashkilotdan farqi (margin) chiqadi;
  - notanish (dev'da boshqa xati yo'q): tarjima variantlari (sender_variants) ichida to'g'ri nom
    bormi — 1-variantmi.
Margin qoidasi (ball past, 1-o'rin 2-o'rindagi boshqa tashkilotdan kamida M oldinda) — joy
SHARTI bilan va shartsiz (blankdagi hudud/davlat tanilgan tashkilot nomida bormi —
sender_variants.same_place): har M uchun nechta to'g'ri va nechta XATO qo'shiladi.
Ekranga FAQAT sonlar, ballar va DOC raqamlari (nomlar emas).

Ishga tushirish: poetry run python -m scripts.rekvizit.explain_senders
"""

from collections import defaultdict

from src.common.text import normalize
from src.engine.model import learn_model
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.sender import SENDER_MODE, SENDER_THRESHOLD, Matcher, header_text
from src.fields.sender_variants import blank_places, page_variants, same_place

MARGINS = (0.10, 0.25)


def main() -> None:
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = load_split()["dev"]
    pages = [get_pages(letters[doc_id]) for doc_id in dev]
    truths = [load_truth(letters[doc_id]) for doc_id in dev]
    blanks = [header_text(p, SENDER_MODE) for p in pages]
    docs = [t.get("rekvizit_document") or {} for t in truths]
    names = [normalize(doc.get("hujjat_junatuvchi_tashkilot")) for doc in docs]

    kinds, details = defaultdict(list), defaultdict(list)
    rule = defaultdict(int)  # (M, joy sharti, "to'g'ri" | "XATO") -> son
    for i, doc_id in enumerate(dev):
        rest = [j for j in range(len(dev)) if j != i]
        model = learn_model([truths[j] for j in rest], [blanks[j] for j in rest])
        matcher = Matcher(model.sender_texts, model.sender_names)
        ranking = matcher.ranked(blanks[i]) if model.sender_texts else []
        scores = [(score, normalize(name)) for score, name in ranking]
        top_score, top = scores[0] if scores else (0.0, None)
        margin = top_score - (scores[1][0] if len(scores) > 1 else 0.0)
        known = names[i] in {normalize(n) for n in model.sender_names}
        if top_score >= SENDER_THRESHOLD:
            kind = "yozildi to'g'ri" if top == names[i] else "yozildi XATO"
        elif not known:
            variants = [normalize(v) for v in page_variants(pages[i])]
            where = (
                "1-variant"
                if variants[:1] == [names[i]]
                else ("2–4-variant" if names[i] in variants else "variantlarda yo'q")
            )
            kind = f"notanish: {where}"
        else:
            kind = "tanish, ball past: 1-o'rin " + ("TO'G'RI" if top == names[i] else "xato")
        place = None
        if top_score < SENDER_THRESHOLD and top:
            name = next(n for _, n in ranking if normalize(n) == top)
            place = same_place(blank_places(pages[i]), name)
            for m in MARGINS:
                if margin >= m:
                    result = "to'g'ri" if top == names[i] else "XATO"
                    rule[m, "shartsiz", result] += 1
                    if place:
                        rule[m, "joy sharti bilan", result] += 1
        kinds[kind].append(doc_id)
        mark = "" if place is None else (" joy+" if place else " joy-")
        details[kind].append(f"{top_score:.2f}/{margin:.2f}{mark}")

    print(f"Jo'natuvchi (rasmiy LOO, dev {len(dev)} xat, chegara {SENDER_THRESHOLD})\n")
    for kind in sorted(kinds, key=lambda k: (not k.startswith("yozildi"), k)):
        print(f"  {kind:<44} {len(kinds[kind]):>3}")
    # notanishlarda 1-o'rin doim xato — margin qoidasi ularda ham yozib yubormasligi kerak
    print("\n  Ball / 2-o'rindagi boshqa tashkilotdan farqi (yozilmaganlar va xatolar):")
    for kind in sorted(kinds):
        if kind != "yozildi to'g'ri":
            print(f"    {kind}: {', '.join(sorted(details[kind], reverse=True))}")
    print("\n  Margin qoidasi (ball < chegara, margin >= M) — qo'shiladigan javoblar:")
    for m in MARGINS:
        for cond in ("shartsiz", "joy sharti bilan"):
            ok, bad = rule[m, cond, "to'g'ri"], rule[m, cond, "XATO"]
            print(f"    M={m:.2f} {cond:<18} to'g'ri +{ok}, XATO +{bad}")

    print("\n  DOC raqamlari:")
    for kind in sorted(kinds):
        if kind != "yozildi to'g'ri":
            print(f"    {kind} ({len(kinds[kind])}): {', '.join(kinds[kind])}")


if __name__ == "__main__":
    main()
