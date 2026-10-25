"""B2: AI natijalarini to'g'ri javoblar (json) bilan solishtirish.

Ekranga FAQAT foizlar chiqadi. Har xat bo'yicha batafsil jadval outputs/ ga yoziladi
(gitignore'da) — uni faqat Ibrohim o'zi ko'radi.

AI natijasi: <papka>/<DOC_id>.json, tuzilishi to'g'ri javob json'i bilan bir xil.
Boshqarma har doim tasks[0].asosiy_ijrochilar_boshqarmalari ga yoziladi (viloyat bo'lsa ham),
kutilgan qiymat esa src.common.schema.expected_boshqarma qoidasi bilan olinadi.
Har maydon aniqligi PDF turi bo'yicha ham chiqadi (1–6-sahifada matn qatlami: hammasida — "matn
qatlamli", hech birida — "skaner", qolgani — "aralash"): skaner xatlar umumiy foizda yo'qolmasin.
"Bir bosishda" (B5.10) — qo'shimcha ko'rsatkich: yozilgan qiymat to'g'ri YOKI to'g'risi takliflar
ichida (xodim bitta bosish bilan tasdiqlaydi). Asosiy ko'rsatkich — aniqlik (faqat yozilgani).

Ishga tushirish:
    poetry run python -m src.evaluation.evaluate outputs/baseline         # dev
    poetry run python -m src.evaluation.evaluate outputs/baseline --test  # test (yakuniy)
"""

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pymupdf
from rapidfuzz import fuzz

from src.common.schema import ALL_FIELDS, REKVIZIT_FIELDS, expected_boshqarma, group_of
from src.common.text import normalize
from src.evaluation.dataset import REAL_DIR, list_letters, load_split, load_truth
from src.reading.pdf_text import has_text_layer, text_layer_words

# Bo'shliqlar ma'noni o'zgartirmaydigan maydonlar ("O.N. Xrushev" == "O.N.Xrushev")
SPACELESS = {"hujjat_sana", "hujjat_raqami", "imzolagan_shaxs"}
DETAIL_COLUMNS = ["doc_id", "maydon", "kutilgan", "ai_javobi", "togri"]
KINDS = ("matn qatlamli", "aralash", "skaner")
KIND_PAGES = 6  # AI shu sahifalarni o'qiydi (engine/pipeline.MAX_PAGES)


def predicted_boshqarma(prediction: dict) -> str | None:
    task = (prediction.get("tasks") or [{}])[0]
    names = task.get("asosiy_ijrochilar_boshqarmalari") or []
    return names[0] if names else None


def true_values(truth: dict) -> dict[str, str | None]:
    """Kalit json'idan 6 ta maydonning to'g'ri javobi."""
    true_doc = truth.get("rekvizit_document") or {}
    values = {field: true_doc.get(field) for field in REKVIZIT_FIELDS}
    values["boshqarma"] = expected_boshqarma(truth)
    return values


def field_values(prediction: dict, truth: dict) -> dict[str, tuple[str | None, str | None]]:
    """Har maydon uchun (AI javobi, to'g'ri javob) juftligi."""
    pred_doc = prediction.get("rekvizit_document") or {}
    expected = true_values(truth)
    values = {field: (pred_doc.get(field), expected[field]) for field in REKVIZIT_FIELDS}
    values["boshqarma"] = (predicted_boshqarma(prediction), expected["boshqarma"])
    return values


def _same(a: str | None, b: str | None, field: str) -> bool:
    spaceless = field in SPACELESS
    return bool(a) and normalize(a, spaceless) == normalize(b, spaceless)


def suggested(prediction: dict, field: str, expected: str | None) -> bool:
    """To'g'ri qiymat shu maydon takliflari ichida bormi."""
    options = (prediction.get("takliflar") or {}).get(field) or []
    options = options if isinstance(options, list) else [options]
    return any(_same(o, expected, field) for o in options)


def compare(answer: dict, truth: dict) -> dict[str, dict]:
    """Test rejimi: har maydon bo'yicha AI javobi va to'g'ri javob (shu modul qoidalari bilan).
    mos: True/False, AI javob bermagan bo'lsa — None ("tekshirish kerak" — xato emas).
    taklif_mos: maydon bo'sh, lekin takliflardan biri to'g'ri bo'lsa — True."""
    suggestions = answer.get("takliflar") or {}
    out = {}
    for field, (predicted, expected) in field_values(answer, truth).items():
        row = {"ai": predicted, "togri": expected, "mos": None}
        if predicted:
            row["mos"] = _same(predicted, expected, field)
        if field in suggestions:
            row["taklif_mos"] = suggested(answer, field, expected)
        out[field] = row
    return out


def pct(part: int, whole: int) -> str:
    return f"{part / whole:6.1%}" if whole else "     —"


@dataclass
class FieldScore:
    """Bitta maydon bo'yicha hisob: nechta xat, nechtasiga javob berildi, nechtasi to'g'ri."""

    total: int = 0
    answered: int = 0
    correct: int = 0
    similarity: float = 0.0  # javob berilganlar bo'yicha o'xshashliklar yig'indisi (har biri 0..1)
    empty_truth: int = 0  # json'da qiymati bo'sh xatlar — faqat bilish uchun
    one_click: int = 0  # yozilgani to'g'ri yoki to'g'risi takliflarda

    def add(
        self,
        predicted: str | None,
        expected: str | None,
        spaceless: bool = False,
        suggested: bool = False,
    ) -> bool:
        self.total += 1
        if not expected:
            self.empty_truth += 1
        is_correct = False
        if predicted:  # yozilmagan — "bilmayman": xato emas, lekin to'g'ri ham emas
            self.answered += 1
            a, b = normalize(predicted, spaceless), normalize(expected, spaceless)
            self.similarity += fuzz.ratio(a, b) / 100
            is_correct = a == b
            self.correct += is_correct
        self.one_click += is_correct or suggested
        return is_correct

    def row(self) -> str:
        sim = f"{self.similarity / self.answered:4.2f}" if self.answered else "   —"
        text = (
            f"aniqlik {pct(self.correct, self.total)} | qamrov {pct(self.answered, self.total)}"
            f" | ishonchlilik {pct(self.correct, self.answered)}"
            f" | bir bosishda {pct(self.one_click, self.total)} | o'xshashlik {sim}"
        )
        if self.empty_truth:
            text += f" | json'da bo'sh: {self.empty_truth}"
        return text


def load_prediction(pred_dir: Path, doc_id: str) -> dict:
    """AI natijasi. Fayl bo'lmasa — bo'sh, ya'ni hamma maydonga "bilmayman"."""
    path = pred_dir / f"{doc_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def evaluate(
    pred_dir: Path, doc_ids: list[str], root: Path = REAL_DIR
) -> tuple[dict[str, FieldScore], dict[str, FieldScore], list[dict]]:
    """Faqat doc_ids dagi xatlarni baholaydi (dev yoki test)."""
    letters = {letter.doc_id: letter for letter in list_letters(root)}
    scores = {field: FieldScore() for field in ALL_FIELDS}
    by_group: dict[str, FieldScore] = defaultdict(FieldScore)
    details = []
    for doc_id in doc_ids:
        truth = load_truth(letters[doc_id])
        prediction = load_prediction(pred_dir, doc_id)
        for field, (predicted, expected) in field_values(prediction, truth).items():
            is_correct = scores[field].add(
                predicted,
                expected,
                spaceless=field in SPACELESS,
                suggested=suggested(prediction, field, expected),
            )
            if field == "boshqarma":
                by_group[group_of(expected)].add(predicted, expected)
            details.append(
                {
                    "doc_id": doc_id,
                    "maydon": field,
                    "kutilgan": expected,
                    "ai_javobi": predicted,
                    "togri": is_correct,
                }
            )
    return scores, dict(by_group), details


def pdf_kind(pdf: Path) -> str:
    """PDF turi: 1–6-sahifaning hammasida matn qatlami bor / hech birida yo'q / aralash."""
    with pymupdf.open(pdf) as doc:
        layers = [has_text_layer(text_layer_words(page)) for page in list(doc)[:KIND_PAGES]]
    return "matn qatlamli" if all(layers) else "skaner" if not any(layers) else "aralash"


def by_kind(details: list[dict], kinds: dict[str, str]) -> dict[tuple[str, str], FieldScore]:
    """(PDF turi, maydon) -> baho (details — evaluate'ning har xat bo'yicha qatorlari)."""
    scores: dict[tuple[str, str], FieldScore] = defaultdict(FieldScore)
    for row in details:
        field = row["maydon"]
        scores[kinds[row["doc_id"]], field].add(
            row["ai_javobi"], row["kutilgan"], spaceless=field in SPACELESS
        )
    return scores


def write_details(details: list[dict], path: Path) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DETAIL_COLUMNS)
        writer.writeheader()
        writer.writerows(details)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI natijalarini baholash")
    parser.add_argument("pred_dir", type=Path, help="AI natijalari papkasi (outputs/...)")
    parser.add_argument("--test", action="store_true", help="TEST to'plamini baholash")
    args = parser.parse_args()

    part = "test" if args.test else "dev"
    if args.test:
        print("⚠️  TEST to'plami: faqat yakuniy o'lchov uchun.")
        print("    Bu natijaga qarab qoida yoki lug'at o'zgartirilmaydi!\n")
    doc_ids = load_split()[part]
    found = sum((args.pred_dir / f"{doc_id}.json").exists() for doc_id in doc_ids)
    scores, by_group, details = evaluate(args.pred_dir, doc_ids)

    print(f"Baholash: {args.pred_dir} | to'plam: {part} ({len(doc_ids)} xat)")
    print(f"AI natijasi topildi: {found}/{len(doc_ids)} xat\n")
    for field in ALL_FIELDS:
        print(f"  {field:<28} {scores[field].row()}")
    print("\n  boshqarma, guruhlar bo'yicha:")
    for group in sorted(by_group):
        print(f"    {group:<9} ({by_group[group].total:>2} xat)  {by_group[group].row()}")

    letters = {letter.doc_id: letter for letter in list_letters()}
    kinds = {doc_id: pdf_kind(letters[doc_id].pdf) for doc_id in doc_ids}
    kind_scores = by_kind(details, kinds)
    counts = {kind: sum(k == kind for k in kinds.values()) for kind in KINDS}
    print("\n  PDF turi bo'yicha aniqlik (to'g'ri / xatlar):")
    print(f"    {'':<28}" + "".join(f"{f'{kind} ({counts[kind]})':>22}" for kind in KINDS))
    for field in ALL_FIELDS:
        cells = []
        for kind in KINDS:
            score = kind_scores[kind, field]
            cell = f"{score.correct}/{score.total} {pct(score.correct, score.total)}"
            cells.append(f"{cell if score.total else '—':>22}")
        print(f"    {field:<28}" + "".join(cells))

    report = Path("outputs") / f"{args.pred_dir.name}_{part}_batafsil.csv"
    write_details(details, report)
    print(f"\nHar xat bo'yicha batafsil (faqat o'zingiz ko'ring, gitga kirmaydi): {report}")


if __name__ == "__main__":
    main()
