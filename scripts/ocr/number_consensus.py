"""Raqam: belgi-belgi ovoz — OCR'lar har xil joyda adashsa, to'g'ri raqamni yig'ib bo'ladimi.

Hozirgi qoida (number_vote) raqamni butunligicha ovozga qo'yadi: "12/3-46" va "12/3-48" — ikki
boshqa nomzod. explain_numbers: yangi 150 xatda to'g'ri raqam 43 tasida hech qayerda o'qilmagan,
23 tasida eng yaqin nomzod 1 belgi farq. Bu skript bir xil SHAKLDAGI nomzodlarni ("99/9-99",
number_template.shape) har o'rinda alohida ovozga qo'yadi: har OCR (va matn qatlami / sahifa
OCR'i — "matn") o'qigan har xil raqami bilan bitta ovoz; eng ko'p OCR o'qigan shakl olinadi,
kamida 2 OCR bo'lishi shart; teng ovozda — VLM aniq savol (vlm-extract) belgisi. Nomzodlar
prototip kabi tashkilot qolipiga moslangan (dev'da qolip bor, yangi xatlarda — yo'q).
Ikki variant: hamma OCR; eski VLM'siz ("vlm" — vlm-extract bilan bitta model, xatosini takrorlaydi).
Hozirgi holat bo'yicha (explain_numbers guruhlari) yig'ilgan raqam: to'g'ri / xato / yig'ilmadi;
"yangi" — hech bir OCR aynan shuni o'qimagan (faqat shundagina yutuq bor). Taklif sifatida
qo'shilsa: bir bosishda qanchaga o'sadi.
Ekranga FAQAT sonlar va (--ids) DOC raqamlari.

Ishga tushirish: poetry run python -m scripts.ocr.number_consensus [--ids]
"""

import argparse
from collections import Counter, defaultdict

from scripts.ocr.explain_numbers import READ, SUGGESTED, WRITTEN, group_of
from scripts.ocr.number_letters import Case, dev_cases, new_cases
from src.fields.number_template import fit_all, key, shape
from src.fields.number_vote import FINDER, number_reading

MATN = "matn"
VARIANTS = (("hamma OCR", ()), ("eski VLM'siz", ("vlm",)))
ROWS = (WRITTEN, "takliflarda", READ, "hech qayerda: 1 belgi farq", "hech qayerda: boshqasi")
COLUMNS = ("xat", "to'g'ri", "xato", "yig'ilmadi", "yangi to'g'ri", "yangi xato")


def voters(case: Case) -> list[tuple[str, set[str]]]:
    """(OCR nomi, uning har xil raqamlari key ko'rinishida) — prototip kabi qolipga moslangan."""
    found = [fit_all(f, case.template) for f in case.found]
    text = fit_all(case.text, case.template)
    out = [
        (reader, {key(v) for v in numbers.values() if v and key(v)})
        for reader, numbers in zip(case.readers, found, strict=True)
    ]
    out.append((MATN, {key(v) for v in text.values() if v and key(v)}))
    return out


def consensus(votes: list[tuple[str, set[str]]], skip: tuple[str, ...] = ()) -> str | None:
    """Eng ko'p OCR o'qigan shakldagi nomzodlar — har o'rinda ko'pchilik belgisi. Shaklni kamida
    2 OCR o'qimagan bo'lsa — None. Teng ovozda VLM aniq savol (FINDER) belgisi, u bo'lmasa —
    birinchi uchragani."""
    by_shape: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for reader, numbers in votes:
        if reader not in skip:
            for number in sorted(numbers):
                by_shape[shape(number)].append((reader, number))
    if not by_shape:
        return None

    def strength(item: tuple[str, list[tuple[str, str]]]) -> tuple[int, bool, str]:
        readers = {reader for reader, _ in item[1]}
        return len(readers), FINDER in readers, item[0]

    form, members = max(by_shape.items(), key=strength)
    if len({reader for reader, _ in members}) < 2:
        return None
    finder = next((number for reader, number in members if reader == FINDER), None)
    chars = []
    for i in range(len(form)):
        count = Counter(number[i] for _, number in members)
        best = max(count.values())
        tied = [c for c, n in count.items() if n == best]
        chars.append(finder[i] if finder and finder[i] in tied else tied[0])
    return "".join(chars)


def row_of(case: Case) -> tuple[str, set[str]]:
    """(hozirgi holat guruhi, hamma nomzodlar) — prototip qoidasi bilan."""
    prefill, suggestions = number_reading(case.readers, case.found, case.text, case.template)
    candidates = set().union(*(numbers for _, numbers in voters(case)))
    group, _ = group_of(prefill, suggestions, dict.fromkeys(candidates), case.truth)
    if group in SUGGESTED:
        return "takliflarda", candidates
    if group.startswith("hech qayerda"):
        near = group.endswith("1 belgi farq")
        return "hech qayerda: 1 belgi farq" if near else "hech qayerda: boshqasi", candidates
    return group, candidates


def measure(label: str, cases: list[Case], ids: bool) -> None:
    print(f"\n  {label} ({len(cases)} xat)")
    for name, skip in VARIANTS:
        counts, gained, broken = Counter(), [], []
        for case in cases:
            row, candidates = row_of(case)
            built = consensus(voters(case), skip)
            right = built is not None and built == key(case.truth)
            kind = "yig'ilmadi" if built is None else "to'g'ri" if right else "xato"
            counts[row, "xat"] += 1
            counts[row, kind] += 1
            if built is not None and built not in candidates:
                counts[row, "yangi to'g'ri" if right else "yangi xato"] += 1
                if right and row not in (WRITTEN, "takliflarda"):
                    gained.append(case.doc_id)
            if row == WRITTEN and kind == "xato":
                broken.append(case.doc_id)
        print(f"    {name}:")
        print(f"      {'hozirgi holat':<32}" + "".join(f"{c:>15}" for c in COLUMNS))
        for row in ROWS:
            line = "".join(f"{counts[row, c]:>15}" for c in COLUMNS)
            print(f"      {row:<32}{line}")
        one_click = sum(counts[row, "xat"] for row in (WRITTEN, "takliflarda"))
        print(
            f"      taklif sifatida qo'shilsa — bir bosishda: {one_click} -> "
            f"{one_click + len(gained)}; to'g'ri yozilganda yig'ilgan xato: {len(broken)}"
        )
        if ids:
            print(f"      yutuq: {', '.join(gained) or '—'}")
            print(f"      to'g'ri yozilgan, yig'ilgan xato: {', '.join(broken) or '—'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", action="store_true", help="yutuq va xavf xatlarining DOC raqami")
    args = parser.parse_args()
    print("Raqam: belgi-belgi ovoz (bir xil shakldagi nomzodlar, har OCR bitta ovoz)")
    measure("dev 70, qolip bilan", dev_cases(), args.ids)
    measure("yangi 150, qolipsiz", new_cases(), args.ids)


if __name__ == "__main__":
    main()
