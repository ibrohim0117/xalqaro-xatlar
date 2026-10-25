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
B5.10 (2-o'lchov): notanishlarda 1-variant va to'g'ri nom TURI (FHDY, adliya bosh boshqarmasi,
vazirlik …), variantlarda yo'q bo'lsa — to'g'ri nom skeleti (qolip so'zlari, qolgani "…") va
blankda nima topilgani; hozir javobsiz qolganlarda "joy bo'yicha tanlash" qoidasi (top-5 dan joyi
mos birinchi tanish tashkilot, ball >= F) qancha to'g'ri va qancha XATO qo'shishi.
Ekranga FAQAT sonlar, ballar, turlar, skeletlar va DOC raqamlari (nomlar emas).

Ishga tushirish: poetry run python -m scripts.rekvizit.explain_senders
"""

import re
from collections import defaultdict

from src.common.text import normalize
from src.engine.model import learn_model
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.regions import prepare
from src.fields.sender import (
    SENDER_MARGIN,
    SENDER_MODE,
    SENDER_THRESHOLD,
    Matcher,
    header_text,
)
from src.fields.sender_variants import (
    AGENCY,
    GOV_FOR_CITIZENS,
    JUSTICE_DEPT,
    JUSTICE_GU,
    MINISTRY,
    MVD,
    RECIPIENT,
    ZAGS,
    blank_places,
    find_country,
    find_region,
    page_variants,
    same_place,
    variants_texts,
)

MARGINS = (0.10, 0.25)
PLACE_FLOORS = (0.0, 0.2, 0.3)  # joy bo'yicha tanlash: nomzod balli kamida F
PLACE_TOP = 5
# Nom turi (qolip oilasi): birinchi mos kelgani; json nomlari ham shu bilan turlanadi
FAMILIES = [
    (r"adliya vazirligi(?:ning)? .+ bosh boshqarmasi", "adliya bosh boshqarmasi"),
    (r"bo'yicha bosh boshqarmasi", "hudud bosh boshqarmasi"),
    (r"hukumati fhd", "hukumat FHDY"),
    (r"fhd\w* hududiy", "FHDY hududiy bo'limi"),
    (r"fhd\w* bo'limi", "FHDY bo'limi"),
    (r"fhd\w* boshqarmasi", "FHDY boshqarmasi"),
    (r"fhd\w* (?:qo'mitasi|xizmati)", "FHDY qo'mita/xizmat"),
    (r"fhd", "FHDY boshqa"),
    (r"\biiv\b|ichki ishlar", "IIV"),
    (r"adliya departamenti", "adliya departamenti"),
    (r"pravitelstvo|hukumat", "hukumat"),
    (r"agentlig", "agentlik"),
    (r"adliya vazirligi$", "vazirlik"),
    (r"adliya", "adliya boshqa"),
]
# Skelet: shu so'zlar ochiq qoladi (qolip va umumiy so'zlar), qolgani (joy nomlari) — "…"
OPEN_TEXT = (
    "rossiya federatsiyasi rf adliya vazirligi vazirligining viloyati viloyat o'lkasi respublikasi "
    "respublika bo'yicha bosh boshqarmasi boshqarma fhdy fhdyo fhda bo'limi bo'lim hududiy "
    "qo'mitasi xizmati iiv departamenti davlat xizmatlari xizmat agentligi hukumati shahar shahri "
    "shahridagi tumani tuman markazi xalq sudi sud prokuraturasi va uchun boshqaruvi palatasi "
    "notarial notariusi idorasi arxivi gk turkmaniston ukraina belarus gruziya xitoy moldova "
    "qozog'iston qirg'iziston tojikiston ozarbayjon armaniston argentina"
)
OPEN_WORDS = set(OPEN_TEXT.split())
BLANK_TYPES = [
    ("adliya GU", JUSTICE_GU),
    ("ZAGS", ZAGS),
    ("IIV", MVD),
    ("departament", JUSTICE_DEPT),
    ("agentlik", AGENCY),
    ("vazirlik", MINISTRY),
    ("GK", GOV_FOR_CITIZENS),
]


def family(name: str | None) -> str:
    """Nom qaysi qolip oilasidan (qiymati emas): "FHDY bo'limi", "vazirlik", "boshqa"."""
    low = normalize(name)
    return next((label for pattern, label in FAMILIES if re.search(pattern, low)), "boshqa")


def skeleton(name: str | None) -> str:
    """Nom tuzilishi: qolip so'zlari ochiq, qolgani "…" ("… viloyati FHDY bo'limi")."""
    words = [w if w in OPEN_WORDS else "…" for w in normalize(name).split()]
    collapsed = [w for k, w in enumerate(words) if not (w == "…" and k and words[k - 1] == "…")]
    return " ".join(collapsed)


def blank_parts(pages) -> str:
    """Blankda nima topildi: davlat, hudud (+/-) va tashkilot turi so'zlari."""
    low = " ".join(RECIPIENT.sub(" ", prepare(text)) for text in variants_texts(pages))
    country = "+" if find_country(low) else "-"
    region = "+" if find_region(low) else "-"
    kinds = ",".join(label for label, rx in BLANK_TYPES if rx.search(low)) or "-"
    return f"davlat{country} hudud{region} tur:{kinds}"


def place_pick(ranking, places: list[str], floor: float) -> str | None:
    """Joy bo'yicha tanlash: top-5 dan blankdagi joyi nomida bor birinchi tashkilot (ball >= F)."""
    for score, name in ranking[:PLACE_TOP]:
        if score >= floor and same_place(places, name):
            return normalize(name)
    return None


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
    unknown_rows, known_rows = [], []
    by_place = defaultdict(list)  # (F, "to'g'ri" | "XATO") -> DOC raqamlari
    for i, doc_id in enumerate(dev):
        rest = [j for j in range(len(dev)) if j != i]
        model = learn_model([truths[j] for j in rest], [blanks[j] for j in rest])
        matcher = Matcher(model.sender_texts, model.sender_names)
        ranking = matcher.ranked(blanks[i]) if model.sender_texts else []
        scores = [(score, normalize(name)) for score, name in ranking]
        top_score, top = scores[0] if scores else (0.0, None)
        margin = top_score - (scores[1][0] if len(scores) > 1 else 0.0)
        known = names[i] in {normalize(n) for n in model.sender_names}
        places = blank_places(pages[i])
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
            first = family(variants[0]) if variants else "variant yo'q"
            row = f"1-variant: {first}; to'g'ri: {family(names[i])}"
            if where == "variantlarda yo'q":
                row += f" '{skeleton(names[i])}'; blankda: {blank_parts(pages[i])}"
            unknown_rows.append((where, doc_id, row))
        else:
            kind = "tanish, ball past: 1-o'rin " + ("TO'G'RI" if top == names[i] else "xato")
            position = next((k + 1 for k, (_, n) in enumerate(scores) if n == names[i]), None)
            passing = [n for _, n in ranking[:PLACE_TOP] if same_place(places, n)]
            right_passes = any(normalize(n) == names[i] for n in passing)
            ball = f"{scores[position - 1][0]:.2f}" if position else "—"
            known_rows.append(
                f"{doc_id}: to'g'risi {position or '—'}-o'rinda (ball {ball}), "
                f"top-{PLACE_TOP} da joyi mos {len(passing)} ta, to'g'risi "
                + ("mos" if right_passes else "mos EMAS")
            )
        place = None
        if top_score < SENDER_THRESHOLD and top:
            name = next(n for _, n in ranking if normalize(n) == top)
            place = same_place(places, name)
            for m in MARGINS:
                if margin >= m:
                    result = "to'g'ri" if top == names[i] else "XATO"
                    rule[m, "shartsiz", result] += 1
                    if place:
                        rule[m, "joy sharti bilan", result] += 1
            if not (margin >= SENDER_MARGIN and place):  # hozir javobsiz — joy bo'yicha tanlash
                for floor in PLACE_FLOORS:
                    if pick := place_pick(ranking, places, floor):
                        by_place[floor, "to'g'ri" if pick == names[i] else "XATO"].append(doc_id)
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

    print("\n  Notanishlar — 1-variant va to'g'ri nom turi:")
    for where, doc_id, row in sorted(unknown_rows):
        print(f"    [{where}] {doc_id}: {row}")
    print("\n  Tanish, ball past — to'g'risi reytingda qayerda:")
    for row in known_rows:
        print(f"    {row}")
    print(f"\n  Joy bo'yicha tanlash (hozir javobsizlarda, top-{PLACE_TOP}, ball >= F):")
    for floor in PLACE_FLOORS:
        ok, bad = by_place[floor, "to'g'ri"], by_place[floor, "XATO"]
        print(f"    F={floor:.1f}  to'g'ri +{len(ok)} ({', '.join(ok)})")
        print(f"           XATO    +{len(bad)} ({', '.join(bad)})")

    print("\n  DOC raqamlari:")
    for kind in sorted(kinds):
        if kind != "yozildi to'g'ri":
            print(f"    {kind} ({len(kinds[kind])}): {', '.join(kinds[kind])}")


if __name__ == "__main__":
    main()
