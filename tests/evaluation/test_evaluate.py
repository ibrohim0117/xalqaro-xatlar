"""src/evaluation/evaluate.py testlari — faqat soxta (to'qilgan) xatlar bilan, real ma'lumotsiz."""

import json
from pathlib import Path

import pymupdf

from src.evaluation.evaluate import FieldScore, by_kind, compare, evaluate, pdf_kind
from tests.conftest import make_letter_pdf, make_scanned_pdf

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


def test_compare_marks_correct_wrong_and_suggestions():
    answer = {
        "rekvizit_document": {
            "hujjat_junatuvchi_tashkilot": None,
            "hujjat_sana": "12.03.2026",
            "hujjat_raqami": None,
            "imzolagan_shaxs": "A.B. Sidorov",
            "hujjatning_qisqacha_mazmuni": "Mazmun",
        },
        "tasks": [{"asosiy_ijrochilar_boshqarmalari": ["Farg'ona viloyati adliya boshqarmasi"]}],
        "takliflar": {"hujjat_raqami": "55/07-1234", "hujjat_junatuvchi_tashkilot": ["A", "B AV"]},
    }
    truth = {
        "rekvizit_document": {
            "hujjat_junatuvchi_tashkilot": "B AV",
            "hujjat_sana": "13.03.2026",
            "hujjat_raqami": "55/07-1234",
            "imzolagan_shaxs": "A.B.Sidorov",
            "hujjatning_qisqacha_mazmuni": "Boshqa mazmun",
        },
        "tasks": [{"asosiy_ijrochilar": ["Farg'ona viloyati adliya boshqarmasi"]}],
    }
    rows = compare(answer, truth)
    assert rows["imzolagan_shaxs"]["mos"] is True  # bo'shliq farqi hisobga olinmaydi
    assert rows["hujjat_sana"]["mos"] is False
    assert rows["hujjatning_qisqacha_mazmuni"]["mos"] is False
    assert rows["boshqarma"]["mos"] is True  # viloyat asosiy_ijrochilar da (evaluate qoidasi)
    assert rows["hujjat_raqami"] == {
        "ai": None,
        "togri": "55/07-1234",
        "mos": None,  # AI yozmagan — "tekshirish kerak", xato emas
        "taklif_mos": True,
    }
    assert rows["hujjat_junatuvchi_tashkilot"]["taklif_mos"] is True  # variantlardan biri to'g'ri


def test_pdf_kind(tmp_path):
    letter = make_letter_pdf(tmp_path / "xat.pdf")  # 2-sahifada matn qatlami yo'q (conftest)
    assert pdf_kind(letter) == "aralash"
    assert pdf_kind(make_scanned_pdf(tmp_path / "skaner.pdf", letter)) == "skaner"
    with pymupdf.open() as doc:  # bitta sahifa, to'liq matn qatlami
        doc.new_page().insert_text((50, 72), "Министерство юстиции Республики Узбекистан. " * 3)
        doc.save(tmp_path / "matn.pdf")
    assert pdf_kind(tmp_path / "matn.pdf") == "matn qatlamli"


def test_scores_by_pdf_kind():
    def row(doc_id, expected, answer):
        signer = "imzolagan_shaxs"
        return {"doc_id": doc_id, "maydon": signer, "kutilgan": expected, "ai_javobi": answer}

    details = [row("A", "A.B.Sidorov", "A.B. Sidorov"), row("B", "O.N.Petrov", None)]
    scores = by_kind(details, {"A": "matn qatlamli", "B": "skaner"})
    assert scores["matn qatlamli", "imzolagan_shaxs"].correct == 1  # bo'shliq farq emas
    assert scores["skaner", "imzolagan_shaxs"].correct == 0
    assert scores["skaner", "imzolagan_shaxs"].total == 1


def test_one_click_counts_correct_or_suggested():
    score = FieldScore()
    score.add("A", "A")  # yozilgan, to'g'ri
    score.add(None, "B", suggested=True)  # yozilmagan, takliflarda bor
    score.add("X", "C")  # yozilgan, xato
    score.add(None, "D")  # yozilmagan, takliflarda yo'q
    assert (score.correct, score.answered, score.one_click, score.total) == (1, 2, 2, 4)
    assert "bir bosishda  50.0%" in score.row()
