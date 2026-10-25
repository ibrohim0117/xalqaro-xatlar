"""B5.5-1: raqam — qaysi OCR va bo'lak to'g'ri o'qiydi, qaysi qoida ko'proq to'g'ri yozadi.
OCR qayta ishlatilmaydi (compare_ocr saqlagan matnlar: outputs/ocr/<OCR>.json).

1) Har OCR va bo'lak (barcha dev xatlarda, saqlangan hamma bo'laklar): nechta raqam berdi, nechtasi
   to'g'ri, nechtasi 1 belgi farq. "matn" — matn qatlami va sahifa OCR'idagi "№" dan keyingi raqam.
2) Qoidalar — prototip sharti bilan (B5.12: OCR hamma xatda, sanasi bosma xatlarda ham); OCR'lar
   faqat prototip o'qiydigan bo'laklarni (date_ocr.crops_for) beradi; "matn" ham bitta ovoz.
     N0 hozirgi: raqam yozilmaydi, bitta taklif (matn qatlami, bo'lmasa sahifa OCR'i);
     N1 matn qatlami raqami (bosma, "№" dan keyin);
     N2 VLM aniq savol — header raqami yolg'iz;
     N3 N2 + boshqa OCR tasdig'i (biror bo'lakda yoki "matn"da shu raqam);
     N4 N3, lekin tasdiq eski VLM'siz (bir model xatosi takrorlanmasin);
     N5 N2, faqat VLM sanasi tasdiqlangan bo'lsa (prefill_date: VLM to'g'ri qatorni topgan);
     N6 N1, bo'lmasa N3;
     N7 VLM o'zi: header raqami line yoki page'dagi bilan bir xil (ikki ko'rinish kelishgan);
     N8 N4 yoki N7;
     N9 matn qatlami raqami, faqat tashkilot qolipiga mos bo'lsa (number_template.matches);
     N10 N9 yoki N4;
     NP prototip qoidasi (number_vote.number_reading) — N4 bilan aynan bir xil chiqishi shart.
   Har qoida ikki xil: qolipsiz va qolip bilan — barcha raqamlar avval tashkilot qolipiga moslanadi
   (number_template.fit; qolip shu tashkilotning BOSHQA dev xatlaridan — fit_numbers.templates).
   N9/N10 faqat qolip bilan ma'noli. "jami" — to'g'ri yozilgan + yozilmaganlarda to'g'ri raqam 3 ta
   taklif ichida (N0 — bitta taklif).
3) Yuqori chegara (barcha xatlar): to'g'ri raqam umuman biror joyda o'qilganmi.
4) VLM header raqami 1–3 belgi farq qilgan xatlar: farq TURI (raqam o'rniga raqam, ajratgich,
   harf/raqam, ortiqcha yoki tushib qolgan belgi) va JOYI — to'g'ri raqam SHAKLIDA (raqam -> 9,
   harf -> A; qiymat emas): X — boshqa belgi o'qilgan, _ — tushib qolgan, + — ortiqcha belgi.
   (Birinchi urinish "oxirgi ajratgichdan keyin/oldin" edi — 99/99-99999/99 da oxirgi bo'lak
   "/99", qo'lda yozilgan 99999 esa o'rtada: noto'g'ri xulosa berardi.) Matn qatlami xatolari.
2b) B5.12: prototip OCR'ni hamma xatda ishlatadi (sanasi bosma xatlarda ham — raqam uchun);
   taqqoslash uchun eski shart (sanasi bosma xatda OCR yo'q), qolip bilan, NP qoidasi: hamma xatda
   va faqat sanasi bosma xatlarda.
5) Qolip bilan N10 to'g'ri yozmagan xatlarda VLM header raqami to'g'risiga nisbatan qanday.
Ekranga FAQAT sonlar chiqadi; --ids — DOC raqamlari (qiymatlarsiz).

Ishga tushirish: poetry run python -m scripts.ocr.number_failures [--ids]
"""

import argparse
import json
import re
from collections import Counter, defaultdict

from rapidfuzz.distance import Levenshtein

from scripts.ocr.compare_ocr import OUT_DIR
from scripts.ocr.fit_numbers import templates
from src.engine.date_ocr import DEFAULT_READERS, crops_for
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_number import date_and_number, date_number_answer
from src.fields.date_vote import (
    WINDOW_DAYS,
    engine_dates,
    in_window,
    prefill_date,
    to_day,
    windowed,
)
from src.fields.number_template import Template, fit_all, matches
from src.fields.number_vote import (
    confirmed_number,
    engine_numbers,
    key,
    number_reading,
    ranked_numbers,
)

READERS = DEFAULT_READERS.split(",")  # prototip bilan bir xil: aniq savol VLM birinchi
CROP_ORDER = ("number", "line", "header", "page", "matn qatlami", "sahifa OCR")
N0, N1, N2, N3, N4, N5, N6, N7, N8, N9, N10 = (
    "N0 hozirgi (faqat taklif)",
    "N1 matn qatlami",
    "N2 VLM header yolg'iz",
    "N3 VLM + tasdiq",
    "N4 N3, eski VLM'siz",
    "N5 VLM, sana tasdiqlangan",
    "N6 N1 yoki N3",
    "N7 VLM 2 ko'rinishda",
    "N8 N4 yoki N7",
    "N9 matn qatlami, qolipga mos",
    "N10 N9 yoki N4",
)
NP = "NP prototip (=N4)"
RULES = (N0, N1, N2, N3, N4, N5, N6, N7, N8, N9, N10, NP)
PLAIN, TEMPLATE = "qolipsiz", "qolip bilan"
SEPARATORS = "/-._\\"


def relation(value: str | None, truth: str) -> str:
    """O'qilgan raqam to'g'risiga nisbatan qanday."""
    if not value:
        return "o'qilmadi"
    read, expected = key(value), key(truth)
    if read == expected:
        return "to'g'ri"
    distance = Levenshtein.distance(read, expected)
    if distance == 1:
        return "1 belgi farq"
    if distance <= 3:
        return "2-3 belgi farq"
    if read in expected or expected in read:
        return "qisman"
    return "boshqa raqam"


def char_kind(char: str) -> str:
    return "raqam" if char.isdigit() else "ajratgich" if char in SEPARATORS else "harf"


def edit_kinds(value: str, truth: str) -> list[str]:
    """O'qilganni to'g'risiga aylantiradigan har tuzatishning turi."""
    read, expected = key(value), key(truth)
    kinds = []
    for op in Levenshtein.editops(read, expected):
        if op.tag == "replace":
            pair = {char_kind(read[op.src_pos]), char_kind(expected[op.dest_pos])}
            kind = {
                frozenset({"raqam"}): "raqam o'rniga raqam",
                frozenset({"ajratgich"}): "ajratgich o'rniga ajratgich",
                frozenset({"harf", "raqam"}): "harf/raqam almashgan",
                frozenset({"harf"}): "harf o'rniga harf",
            }.get(frozenset(pair), "ajratgich/belgi almashgan")
        elif op.tag == "delete":
            kind = f"ortiqcha {char_kind(read[op.src_pos])}"
        else:
            kind = f"tushib qolgan {char_kind(expected[op.dest_pos])}"
        kinds.append(kind)
    return kinds


def error_shape(value: str, truth: str) -> str:
    """To'g'ri raqam shakli (raqam -> 9, harf -> A), xato joylari belgilangan: X — boshqa belgi
    o'qilgan, _ — tushib qolgan, + — shu joyda ortiqcha belgi. Qiymat chiqmaydi — faqat shakl."""
    read, expected = key(value), key(truth)
    marks = ["9" if c.isdigit() else c if c in SEPARATORS else "A" for c in expected]
    extra = Counter()
    for op in Levenshtein.editops(read, expected):
        if op.tag == "replace":
            marks[op.dest_pos] = "X"
        elif op.tag == "insert":
            marks[op.dest_pos] = "_"
        else:
            extra[op.dest_pos] += 1
    return "".join("+" * extra[i] + m for i, m in enumerate(marks)) + "+" * extra[len(marks)]


def digits(value: str | None) -> str:
    """Faqat raqamlar (ajratgich va harflarsiz) — format farqini o'qish xatosidan ajratish uchun."""
    return re.sub(r"\D", "", key(value))


def views_agree(vlm: dict[str, str | None]) -> str | None:
    """VLM header raqami line yoki page'dagi bilan bir xil bo'lsa — o'sha raqam."""
    header = vlm.get("header")
    others = {key(vlm[crop]) for crop in ("line", "page") if vlm.get(crop)}
    return header if header and key(header) in others else None


def rules(
    found: list[dict[str, str | None]],
    text: dict[str, str | None],
    vlm_date_ok: bool,
    template: Template | None = None,
) -> dict[str, str | None]:
    """Har qoida yozadigan raqam. found — OCR'lar raqamlari (READERS tartibida; OCR ishlamagan
    bo'lsa — bo'sh), text — matn qatlami va sahifa OCR'idagi raqam, template — tashkilot qolipi."""
    confirmed = confirmed_number([*found, text])
    without_old = [f for name, f in zip(READERS, found, strict=True) if name != "vlm"]
    strict = confirmed_number([*without_old, text])
    printed = text["matn qatlami"]
    valid = printed if template and printed and matches(printed, template) else None
    return {
        N0: None,
        N1: text["matn qatlami"],
        N2: found[0].get("header"),
        N3: confirmed,
        N4: strict,
        N5: found[0].get("header") if vlm_date_ok else None,
        N6: text["matn qatlami"] or confirmed,
        N7: views_agree(found[0]),
        N8: strict or views_agree(found[0]),
        N9: valid,
        N10: valid or strict,
        NP: number_reading(READERS, found, text, template)[0],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", action="store_true", help="xato va topilmagan DOC raqamlari")
    args = parser.parse_args()
    letters = {letter.doc_id: letter for letter in list_letters()}
    dev = sorted(load_split()["dev"])
    saved = {r: json.loads((OUT_DIR / f"{r}.json").read_text(encoding="utf-8")) for r in READERS}
    truths = {d: load_truth(letters[d]).get("rekvizit_document") or {} for d in dev}
    learned = templates(truths)  # har xatga — shu tashkilotning boshqa xatlaridan
    quality = defaultdict(Counter)  # (OCR, bo'lak) -> relation soni
    stats = Counter()  # (qolipsiz | qolip bilan, qoida, "auto" | "auto_ok" | "top3")
    wrong = defaultdict(list)  # (variant, qoida) -> avtomatik xato bergan xatlar
    misses = defaultdict(list)  # (N10 holati, VLM header'da nima) -> xatlar
    reachable = Counter()  # yuqori chegara: to'g'ri raqam qayerdadir o'qilganmi
    edits, shapes, near = Counter(), Counter(), 0  # VLM header 1–3 belgi farq: turi, joyi, xatlar
    digits_only, text_layer_errors = 0, Counter()
    used = 0
    always = Counter()  # (guruh, "eski" | "hozirgi", holat) -> son
    for doc_id in dev:
        document = truths[doc_id]
        truth = document.get("hujjat_raqami")
        if not truth:
            continue
        used += 1
        received = to_day(document.get("kirish_sana"))
        first = get_pages(letters[doc_id])[0]
        tl_date, tl_number = date_and_number(first.text_layer)
        text = {
            "matn qatlami": tl_number,
            "sahifa OCR": date_and_number(first.ocr)[1] if first.ocr else None,
        }
        raw = [saved[r].get(doc_id, {}) for r in READERS]

        # 1) har OCR va bo'lak — barcha xatlarda, saqlangan hamma bo'laklar
        for reader, texts in zip(READERS, raw, strict=True):
            for crop, value in engine_numbers(texts).items():
                quality[reader, crop][relation(value, truth)] += 1
        for source, value in text.items():
            quality["matn", source][relation(value, truth)] += 1

        # 3) va 4) — barcha xatlar, saqlangan hamma bo'laklar
        every = [engine_numbers(texts) for texts in raw]
        reachable["VLM ko'rinishlaridan birida"] += key(truth) in {
            key(v) for v in every[0].values() if v
        }
        reachable["biror OCR, bo'lak yoki matnda"] += key(truth) in {
            key(v) for f in [*every, text] for v in f.values() if v
        }
        header = every[0].get("header")
        if header and key(header) != key(truth):
            digits_only += digits(header) == digits(truth)
            if 1 <= Levenshtein.distance(key(header), key(truth)) <= 3:
                near += 1
                edits.update(edit_kinds(header, truth))
                shapes[error_shape(header, truth)] += 1
        if text["matn qatlami"] and key(text["matn qatlami"]) != key(truth):
            text_layer_errors[relation(text["matn qatlami"], truth)] += 1

        # 2) prototip sharti (B5.12): OCR hamma xatda ishlaydi; har OCR faqat o'z bo'laklarini
        printed = in_window(tl_date, received, WINDOW_DAYS)  # sana bosma (matn qatlamida)
        own = [
            {crop: t for crop, t in texts.items() if crop in crops_for(reader)}
            for reader, texts in zip(READERS, raw, strict=True)
        ]
        found = [engine_numbers(texts) for texts in own]
        dates = [windowed(engine_dates(texts), received) for texts in own]
        vlm_date_ok = prefill_date(dates, READERS[0]) is not None
        current = date_number_answer(first)[1].get("hujjat_raqami")
        template = learned[doc_id]
        for variant, use in ((PLAIN, None), (TEMPLATE, template)):
            found_v = [fit_all(f, use) for f in found]
            text_v = fit_all(text, use)
            written = rules(found_v, text_v, vlm_date_ok, use)
            suggestions = ranked_numbers([*found_v, text_v])
            for name, value in written.items():
                hints = ([current] if current else []) if name == N0 else suggestions
                if value:
                    stats[variant, name, "auto"] += 1
                    if key(value) == key(truth):
                        stats[variant, name, "auto_ok"] += 1
                    else:
                        wrong[variant, name].append(doc_id)
                else:
                    stats[variant, name, "top3"] += any(key(h) == key(truth) for h in hints)

        # 2b) eski shart (sanasi bosma xatda OCR yo'q) va hozirgi — NP, qolip bilan
        nothing = [fit_all(engine_numbers({}), template) for _ in READERS]
        old_found = nothing if printed else [fit_all(f, template) for f in found]
        text_t = fit_all(text, template)
        runs = {
            "eski": (
                number_reading(READERS, old_found, text_t, template)[0],
                ranked_numbers([*old_found, text_t]),
            ),
            "hozirgi": (written[NP], suggestions),
        }
        for group in ["hamma xat"] + (["sanasi bosma"] if printed else []):
            always[group, "xat"] += 1
            for run, (value, hints) in runs.items():
                if value:
                    ok = key(value) == key(truth)
                    always[group, run, "yozildi"] += 1
                    always[group, run, "to'g'ri" if ok else "xato"] += 1
                    always[group, run, "jami"] += ok
                else:
                    always[group, run, "jami"] += any(key(h) == key(truth) for h in hints)

        # 5) qolip bilan N10 to'g'ri yozmagan xatlar: VLM header'da nima ko'rgan (written,
        # suggestions — oxirgi, ya'ni qolip bilan variantniki)
        best = written[N10]
        if best and key(best) == key(truth):
            continue
        if best:
            case = "yozildi xato"
        elif any(key(h) == key(truth) for h in suggestions):
            case = "faqat takliflarda"
        else:
            case = "topilmadi"
        seen = relation(found[0].get("header"), truth)
        misses[case, seen].append(doc_id)

    print(f"Raqam: OCR'lar va qoidalar, dev {used} xat (json'da raqam bor)\n")
    print("  1) Har OCR va bo'lak (barcha xatlar):")
    print(f"     {'OCR':<16}{'bo`lak':<14}{'javob':>6}{'to`g`ri':>9}{'1 belgi farq':>14}")
    order = [*READERS, "matn"]
    for reader, crop in sorted(quality, key=lambda s: (order.index(s[0]), CROP_ORDER.index(s[1]))):
        q = quality[reader, crop]
        answered = sum(q.values()) - q["o'qilmadi"]
        print(f"     {reader:<16}{crop:<14}{answered:>6}{q["to'g'ri"]:>9}{q['1 belgi farq']:>14}")

    with_template = sum(t is not None for d, t in learned.items() if truths[d].get("hujjat_raqami"))
    print(f"\n  2) Qoidalar (prototip sharti: OCR hamma xatda; qolip {with_template} xatda):")
    columns = f"{'yozildi':>8}{'to`g`ri':>8}{'xato':>6}{'jami':>6}"
    print(f"     {'':<30}{PLAIN:^28}  {TEMPLATE:^28}")
    print(f"     {'qoida':<30}{columns}  {columns}")
    for name in RULES:
        cells = []
        for variant in (PLAIN, TEMPLATE):
            auto, ok = stats[variant, name, "auto"], stats[variant, name, "auto_ok"]
            jami = ok + stats[variant, name, "top3"]
            cells.append(f"{auto:>8}{ok:>8}{auto - ok:>6}{jami:>6}")
        print(f"     {name:<30}{cells[0]}  {cells[1]}")

    print("\n  2b) Sanasi bosma xatlarda OCR: eski (yo'q) va hozirgi (bor), qolip bilan, NP:")
    print(f"     {'':<36}{'yozildi':>8}{'to`g`ri':>8}{'xato':>6}{'jami':>6}")
    for group in ("hamma xat", "sanasi bosma"):
        for run in ("eski", "hozirgi"):
            cells = "".join(
                f"{always[group, run, k]:>{w}}"
                for k, w in (("yozildi", 8), ("to'g'ri", 8), ("xato", 6), ("jami", 6))
            )
            print(f"     {f'{group} ({always[group, "xat"]}), {run}':<36}{cells}")
    print(f"\n  3) Yuqori chegara ({used} xat): to'g'ri raqam o'qilgan —")
    for where, n in reachable.items():
        print(f"     {where}: {n}")

    print(f"\n  4) VLM header raqami 1–3 belgi farq qilgan {near} xat — tuzatishlar:")
    print("     turi:  " + (", ".join(f"{k} {n}" for k, n in edits.most_common()) or "—"))
    print("     joyi (to'g'ri raqam shakli; X — boshqa belgi, _ — tushib qolgan, + — ortiqcha):")
    for shape, n in sorted(shapes.items(), key=lambda item: (-item[1], item[0])):
        print(f"       {shape:<24} {n}")
    print(f"     faqat raqamlar solishtirilsa to'g'ri (format farqi): {digits_only}")
    row = ", ".join(f"{k} {n}" for k, n in text_layer_errors.most_common()) or "—"
    print(f"     matn qatlami xatolari: {row}")

    print(f"\n  5) Qolip bilan {N10} to'g'ri yozmagan xatlar — VLM header'da nima ko'rgan:")
    for case in ("yozildi xato", "faqat takliflarda", "topilmadi"):
        kinds = Counter({seen: len(docs) for (c, seen), docs in misses.items() if c == case})
        row = ", ".join(f"{seen} {n}" for seen, n in sorted(kinds.items())) or "—"
        print(f"     {case:<18} {sum(kinds.values()):>3}: {row}")

    if args.ids:
        print("\n  Avtomatik xatolar (DOC raqamlari):")
        for variant, name in ((PLAIN, N4), (TEMPLATE, N4), (TEMPLATE, N9), (TEMPLATE, N10)):
            label = f"{name} ({variant})"
            print(f"     {label:<40} {', '.join(wrong[variant, name]) or '—'}")
        print(f"\n  Qolip bilan {N10} to'g'ri yozmaganlar (holat, VLM header'da nima):")
        for (case, seen), docs in sorted(misses.items()):
            print(f"     {case}, {seen} ({len(docs)}): {', '.join(docs)}")


if __name__ == "__main__":
    main()
