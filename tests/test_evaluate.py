"""src/evaluate.py testlari — faqat soxta (to'qilgan) xatlar bilan, real ma'lumotsiz."""

import json
from pathlib import Path

from src.evaluate import FieldScore, evaluate, normalize

VILOYAT = "Soxta viloyati adliya boshqarmasi"
NOTARIAT = "Notariat, advokatura va mediatsiya boshqarmasi"


def make_letter(root: Path, doc_id: str, sana: str, boshqarma: str) -> None:
    """Real json tuzilishidagi soxta xat: viloyat asosiy_ijrochilar'da, qolgani bo'lim maydonida."""
    if boshqarma == VILOYAT:
        task = {"asosiy_ijrochilar": [VILOYAT], "asosiy_ijrochilar_boshqarmalari": []}
    else:
        task = {
            "asosiy_ijrochilar": ["SOXTA XODIM"],
            "asosiy_ijrochilar_boshqarmalari": [boshqarma],
        }
    truth = {
        "rekvizit_document": {"hujjat_sana": sana, "hujjat_raqami": "54/07-16606"},
        "tasks": [task],
    }
    folder = root / doc_id
    folder.mkdir(parents=True)
    (folder / "xat.pdf").write_bytes(b"%PDF-soxta")
    (folder / "xat.json").write_text(json.dumps(truth), encoding="utf-8")


def make_prediction(pred_dir: Path, doc_id: str, sana: str, raqam: str, boshqarma: str) -> None:
    prediction = {
        "rekvizit_document": {"hujjat_sana": sana, "hujjat_raqami": raqam},
        "tasks": [{"asosiy_ijrochilar_boshqarmalari": [boshqarma]}],
    }
    pred_dir.mkdir(exist_ok=True)
    (pred_dir / f"{doc_id}.json").write_text(json.dumps(prediction), encoding="utf-8")


def counts(score: FieldScore) -> tuple[int, int, int]:
    return score.total, score.answered, score.correct


def test_normalize_ignores_harmless_differences():
    assert normalize("O.N. Xrushev", spaceless=True) == normalize("O.N.Xrushev", spaceless=True)
    assert normalize("54/07–16606") == normalize("54/07-16606")  # uzun chiziq
    assert normalize("Bo‘yicha") == normalize("Bo'yicha")  # apostrof turi
    assert normalize("  Xalqaro  huquqiy yordam. ") == "xalqaro huquqiy yordam"
    assert normalize(None) == ""


def test_normalize_keeps_real_differences():
    assert normalize("Toshkent shahri") != normalize("Toshkent viloyati")
    assert normalize("01.10.2026", spaceless=True) != normalize("10.01.2026", spaceless=True)


def test_field_score_separates_unknown_from_wrong():
    score = FieldScore()
    score.add("A", "A")  # to'g'ri
    score.add("B", "A")  # xato
    score.add(None, "A")  # bilmayman
    score.add("", "A")  # bilmayman
    assert counts(score) == (4, 2, 1)
    row = score.row()
    assert "aniqlik  25.0%" in row  # 1 / 4
    assert "qamrov  50.0%" in row  # 2 / 4
    assert "ishonchlilik  50.0%" in row  # 1 / 2


def test_evaluate_counts_only_given_letters(tmp_path):
    real, preds = tmp_path / "real", tmp_path / "preds"
    make_letter(real, "DOC_1", "01.10.2026", VILOYAT)
    make_letter(real, "DOC_2", "02.10.2026", VILOYAT)
    make_letter(real, "DOC_3", "03.10.2026", NOTARIAT)
    make_letter(real, "DOC_4", "04.10.2026", NOTARIAT)  # test to'plamida, baholanmasligi kerak

    make_prediction(preds, "DOC_1", "01.10.2026", "54/07–16606", VILOYAT)  # hammasi to'g'ri
    make_prediction(preds, "DOC_2", "20.10.2026", "54/07-16606", NOTARIAT)  # sana, boshqarma xato
    # DOC_3 uchun AI natijasi yo'q -> hamma maydonga "bilmayman"

    scores, by_group, details = evaluate(preds, ["DOC_1", "DOC_2", "DOC_3"], root=real)

    assert counts(scores["hujjat_sana"]) == (3, 2, 1)
    assert counts(scores["hujjat_raqami"]) == (3, 2, 2)
    assert counts(scores["boshqarma"]) == (3, 2, 1)
    assert counts(scores["imzolagan_shaxs"]) == (3, 0, 0)
    assert scores["imzolagan_shaxs"].empty_truth == 3  # soxta json'da bu maydon yo'q
    assert counts(by_group["viloyat"]) == (2, 2, 1)
    assert counts(by_group["notariat"]) == (1, 0, 0)
    assert len(details) == 3 * 6  # 3 xat x 6 maydon, DOC_4 kirmagan
