"""Sana yozish qoidasi variantlari — dev 70 va yangi xatlarda, OCR'siz (saqlangan matnlardan).

27.10 (Кызмат blanki, explain_date_choice): VLM'ning ikki savoli (vlm-extract va vlm — bitta model)
bir xil xato sana berib, bir-birini "tasdiqlagan"; mustaqil OCR'lar (RapidOCR, Apple Vision) esa
to'g'ri o'qigan. Variantlar (qoidalar src'dan — prototip bilan bitta joyda):
  A — eski qoida (27.10 gacha; prefill_date readers'siz): topuvchi sanasi + istalgan OCR tasdig'i;
  B — tasdiq faqat MUSTAQIL OCR'dan: VLM'ning ikkinchi savoli hisob emas (raqamdagidek);
  C — PROTOTIP (27.10 dan; prefill_date + readers, date_vote.rival_dates): A, lekin kamida 2
      mustaqil OCR boshqa sanaga kelishgan va u ko'proq ovoz olgan bo'lsa — yozilmaydi;
  D — C, lekin ziddiyatda mustaqillar sanasi yoziladi (27.10: rad — dev'da 4 ta to'g'ri -> xato).
Takliflar ikki xil (bir bosishda uchun): hozirgi — har OCR bir ovoz; "VLM bitta ovoz" — VLM'ning
ikki savoli birlashadi. Teng ovozda — OCR tartibi (prototipda hozir tasodifiy: set tartibi).
Matn qatlamidagi bosma sana (avtomatik) hamma variantda o'sha.

Manbalar:
  dev 70 — outputs/ocr/<OCR>.json (compare_ocr); date_failures shaklida A — 54 / 2 / 9 / 5 (26.10),
           C — date_failures'ning 27.10 dan natijasi bilan bir xil;
  yangi xatlar — outputs/vaqt/<nom>/ocr/<DOC>.json (measure_time saqlaydi) va papkadagi json;
           prototip saqlagan javob qaysi qoida bilan mos (27.10 gacha o'lchov — A, keyin — C).
Ekranga FAQAT sonlar; --ids — A ga nisbatan o'zgargan xatlarning DOC raqamlari.

Ishga tushirish (VLM yoqilgan bo'lsin — yangi xatlar uchun matnlar kerak):
    poetry run python -m scripts.prototype.measure_time outputs/papkalar/real2_25 --name sana
    poetry run python -m scripts.ocr.compare_date_rules --name sana [--ids]
"""

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scripts.ocr.compare_ocr import OUT_DIR as OCR_DIR
from scripts.ocr.date_failures import READERS
from scripts.prototype.measure_time import OUT_DIR as TIME_DIR
from src.engine.date_ocr import crops_for
from src.evaluation.dataset import list_letters, load_split, load_truth
from src.evaluation.text_cache import get_pages
from src.fields.date_number import date_and_number
from src.fields.date_vote import (
    FINDERS,
    WINDOW_DAYS,
    engine_dates,
    first_date,
    in_window,
    prefill_date,
    rival_dates,
    same_model,
    to_day,
    windowed,
)

DEFAULT_FOLDER = Path("outputs/papkalar/real2_25")
STATUSES = ("to'g'ri", "xato", "bo'sh")
Found = list[dict[str, str | None]]  # har OCR'ning sana nomzodlari (date_vote.engine_dates)


@dataclass
class Case:
    doc_id: str
    truth: str | None
    auto: str | None  # matn qatlamidan bosma sana (oyna ichida) — avtomatik
    readers: list[str]  # ishlagan OCR'lar, tartib bilan (1-si — topuvchi)
    found: Found
    answer: str | None = None  # prototip saqlagan javobdagi sana (faqat yangi xatlar)
    has_answer: bool = False  # prototip javobi saqlanganmi (measure_time)


def is_vlm(reader: str) -> bool:
    """VLM'ning savollari (vlm-extract, vlm, …) — bitta model: bir-birini tasdiqlasa, bu mustaqil
    tasdiq emas."""
    return reader.startswith("vlm")


def dates_of(candidates: dict[str, str | None]) -> list[str]:
    """Bitta OCR ko'rgan sanalar — takrorsiz, bo'laklar tartibida."""
    return list(dict.fromkeys(d for d in candidates.values() if d))


# ── Yozish qoidalari ──


def rule_a(readers: list[str], found: Found) -> str | None:
    """Eski qoida (27.10 gacha): ziddiyat tekshiruvisiz."""
    return prefill_date(found, readers[0] if readers else None)


def rule_b(readers: list[str], found: Found) -> str | None:
    """Topuvchi sanasi — faqat mustaqil OCR tasdiqlasa."""
    if not readers or readers[0] not in FINDERS:
        return rule_a(readers, found)
    date = first_date(found, FINDERS[readers[0]])
    independent = (
        f for r, f in zip(readers[1:], found[1:], strict=True) if not same_model(r, readers[0])
    )
    return date if date and any(date in dates_of(f) for f in independent) else None


AMBIGUOUS = "?"  # bir nechta raqib sana teng ovozda


def rival(readers: list[str], found: Found, written: str | None) -> str | None:
    """Mustaqil OCR'lar kelishgan boshqa sana: kamida 2 ovoz va yozilgan sanadan ko'p. Bitta
    bo'lsa — o'sha, bir nechtasi teng bo'lsa — AMBIGUOUS, yo'q bo'lsa — None."""
    rivals = rival_dates(found, readers, written) if written and readers else []
    if not rivals:
        return None
    top = [d for d, n in rivals if n == rivals[0][1]]
    return top[0] if len(top) == 1 else AMBIGUOUS


def rule_c(readers: list[str], found: Found) -> str | None:
    """Prototip (27.10 dan): A, lekin mustaqillar boshqa sanaga kelishgan bo'lsa — yozilmaydi."""
    return prefill_date(found, readers[0] if readers else None, readers)


def rule_d(readers: list[str], found: Found) -> str | None:
    """C, lekin ziddiyatda mustaqillar kelishgan sana (aniq ustun bo'lsa) yoziladi."""
    written = rule_a(readers, found)
    other = rival(readers, found, written)
    if other is None:
        return written
    return None if other == AMBIGUOUS else other


RULES: dict[str, Callable[[list[str], Found], str | None]] = {
    "A eski (27.10 gacha)": rule_a,
    "B mustaqil tasdiq": rule_b,
    "C prototip (27.10 dan)": rule_c,
    "D ziddiyatda (rad)": rule_d,
}


# ── Takliflar ──


def suggestions(readers: list[str], found: Found, one_vlm: bool = False, k: int = 3) -> list[str]:
    """Ko'proq OCR ko'rgan k ta sana; one_vlm — VLM'ning savollari bitta ovoz. Teng ovozda — OCR va
    bo'lak tartibi (date_vote.ranked'dan farqi: tasodifiy emas)."""
    groups: dict[str, list[str]] = {}
    for reader, candidates in zip(readers, found, strict=True):
        group = groups.setdefault("vlm" if one_vlm and is_vlm(reader) else reader, [])
        group += [d for d in dates_of(candidates) if d not in group]
    counts, order = Counter(), {}
    for dates in groups.values():
        for d in dates:
            counts[d] += 1
            order.setdefault(d, len(order))
    return sorted(counts, key=lambda d: (-counts[d], order[d]))[:k]


# ── Holat va hisob ──


def written_by(case: Case, rule) -> str | None:
    return case.auto if case.auto else rule(case.readers, case.found)


def status(value: str | None, truth: str | None) -> str:
    if not value:
        return "bo'sh"
    return "to'g'ri" if value == truth else "xato"


def one_click(case: Case, value: str | None, one_vlm: bool) -> bool:
    """Yozilgani to'g'ri yoki to'g'risi takliflarda (avtomatik sanada taklif bo'lmaydi)."""
    if value == case.truth:
        return True
    return not case.auto and case.truth in suggestions(case.readers, case.found, one_vlm)


def report(title: str, cases: list[Case], show_ids: bool) -> None:
    n = len(cases)
    print(f"\n{title}: {n} xat, bosma sana (avtomatik) {sum(bool(c.auto) for c in cases)}")
    if not n:
        return
    base = {c.doc_id: status(written_by(c, rule_a), c.truth) for c in cases}
    head = (
        f"{'yozildi':>8}{'to`g`ri':>9}{'xato':>6}{'bo`sh':>7}{'bir bosishda':>15}{'VLM 1 ovoz':>12}"
    )
    print(f"  {'variant':<26}{head}")
    moves: dict[str, Counter] = {}
    ids: dict[tuple[str, str], list[str]] = defaultdict(list)
    for name, rule in RULES.items():
        counts, clicks, clicks_one, moved = Counter(), 0, 0, Counter()
        for case in cases:
            value = written_by(case, rule)
            now = status(value, case.truth)
            counts[now] += 1
            clicks += one_click(case, value, one_vlm=False)
            clicks_one += one_click(case, value, one_vlm=True)
            if now != base[case.doc_id]:
                change = f"{base[case.doc_id]} → {now}"
                moved[change] += 1
                ids[name, change].append(case.doc_id)
        moves[name] = moved
        written = counts["to'g'ri"] + counts["xato"]
        print(
            f"  {name:<26}{written:>8}{counts["to'g'ri"]:>9}{counts['xato']:>6}{counts["bo'sh"]:>7}"
            f"{f'{clicks}/{n}':>15}{f'{clicks_one}/{n}':>12}"
        )
    print("  A ga nisbatan o'zgarishlar (soni):")
    for name, moved in moves.items():
        if name.startswith("A"):
            continue
        row = ", ".join(f"{change} {k}" for change, k in sorted(moved.items())) or "o'zgarish yo'q"
        print(f"    {name:<26} {row}")
        if show_ids:
            for change in sorted(moved):
                print(f"      {change}: {', '.join(ids[name, change])}")


def date_failures_line(cases: list[Case], rule=rule_a) -> str:
    """Natija date_failures shaklida: yozildi to'g'ri / xato / faqat takliflarda / topilmadi."""
    out = Counter()
    for case in cases:
        value = written_by(case, rule)
        if value:
            out["to'g'ri" if value == case.truth else "xato"] += 1
        elif case.truth in suggestions(case.readers, case.found):
            out["takliflarda"] += 1
        else:
            out["topilmadi"] += 1
    return " / ".join(str(out[k]) for k in ("to'g'ri", "xato", "takliflarda", "topilmadi"))


# ── Manbalar ──


def dev_cases() -> list[Case]:
    """dev 70: compare_ocr saqlagan matnlar, date_failures'dagidek (o'sha OCR'lar va bo'laklar)."""
    readers = [r for r in READERS if (OCR_DIR / f"{r}.json").exists()]
    saved = {r: json.loads((OCR_DIR / f"{r}.json").read_text(encoding="utf-8")) for r in readers}
    letters = {letter.doc_id: letter for letter in list_letters()}
    cases = []
    for doc_id in sorted(load_split()["dev"]):
        document = load_truth(letters[doc_id]).get("rekvizit_document") or {}
        received = to_day(document.get("kirish_sana"))
        text_layer = date_and_number(get_pages(letters[doc_id])[0].text_layer)[0]
        texts = [
            {crop: t for crop, t in saved[r].get(doc_id, {}).items() if crop in crops_for(r)}
            for r in readers
        ]
        cases.append(
            Case(
                doc_id,
                document.get("hujjat_sana"),
                text_layer if in_window(text_layer, received, WINDOW_DAYS) else None,
                readers,
                [windowed(engine_dates(t), received) for t in texts],
            )
        )
    return cases


def load_saved(path: Path) -> tuple[list[str], dict[str, dict[str, str]], str | None, str]:
    """measure_time.save_reading yozgan fayl: (OCR'lar, matnlar, bosma sana, kelgan sana)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["readers"], data["texts"], data["auto"], data["received"]


def new_cases(folder: Path, name: str) -> tuple[list[Case], int]:
    """Yangi xatlar: measure_time saqlagan matnlar. (holatlar, matni saqlanmagan xatlar soni)."""
    cases, missing = [], 0
    for letter in list_letters(folder):
        path = TIME_DIR / name / "ocr" / f"{letter.doc_id}.json"
        if not path.exists():
            missing += 1
            continue
        readers, texts, auto, received = load_saved(path)
        day = to_day(received)
        answer_path = TIME_DIR / name / f"{letter.doc_id}.json"
        answer = json.loads(answer_path.read_text(encoding="utf-8")) if answer_path.exists() else {}
        cases.append(
            Case(
                letter.doc_id,
                (load_truth(letter).get("rekvizit_document") or {}).get("hujjat_sana"),
                auto,
                readers,
                [windowed(engine_dates(texts[r]), day) for r in readers],
                (answer.get("rekvizit_document") or {}).get("hujjat_sana"),
                answer_path.exists(),
            )
        )
    return cases, missing


def main() -> None:
    parser = argparse.ArgumentParser(description="Sana yozish qoidasi variantlari (faqat sonlar)")
    parser.add_argument("--name", default="sana", help="measure_time o'lchovi: outputs/vaqt/<nom>")
    parser.add_argument("--folder", type=Path, default=DEFAULT_FOLDER, help="yangi xatlar papkasi")
    parser.add_argument("--ids", action="store_true", help="o'zgargan xatlarning DOC raqamlari")
    args = parser.parse_args()

    dev = dev_cases()
    report("dev 70 (outputs/ocr)", dev, args.ids)
    print(f"  tekshiruv (date_failures shaklida): A {date_failures_line(dev)} (26.10: 54/2/9/5),")
    print(f"    C (prototip) {date_failures_line(dev, rule_c)} — date_failures hozir shuni beradi")

    cases, missing = new_cases(args.folder, args.name)
    report(f"yangi xatlar ({args.folder}, o'lchov {args.name})", cases, args.ids)
    if missing:
        print(f"  matni saqlanmagan: {missing} xat — avval measure_time --name {args.name}")
    with_answer = [c for c in cases if c.has_answer]
    same_a = sum(written_by(c, rule_a) == c.answer for c in with_answer)
    same_c = sum(written_by(c, rule_c) == c.answer for c in with_answer)
    print(
        f"  tekshiruv: prototip javobidagi sana bilan mos — A {same_a}/{len(with_answer)},"
        f" C {same_c}/{len(with_answer)} (o'lchov 27.10 gacha bo'lsa A, keyin C to'liq mos)"
    )


if __name__ == "__main__":
    main()
