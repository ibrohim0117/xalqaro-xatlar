"""scripts/ocr/date_failures.py testlari — to'qilgan OCR matnlari bilan."""

from datetime import date

from scripts.ocr.date_failures import outcome

RECEIVED, TRUTH = date(2026, 1, 9), "19.12.2025"


def test_outcomes_follow_the_prototype_rule():
    vlm_ok, rapid_ok = {"date": "19.12.2025"}, {"line": "19.12.2025 № 54"}
    assert outcome([{}, {}], "19.12.2025", TRUTH, RECEIVED) == "yozildi to'g'ri"  # matn qatlami
    assert outcome([vlm_ok, rapid_ok], None, TRUTH, RECEIVED) == "yozildi to'g'ri"  # VLM + tasdiq
    wrong = {"date": "09.12.2025"}
    assert outcome([wrong, wrong], None, TRUTH, RECEIVED) == "yozildi xato"
    assert outcome([vlm_ok, {"date": "01.12.2025"}], None, TRUTH, RECEIVED) == "faqat takliflarda"
    assert outcome([{"date": "№ 54"}, {}], None, TRUTH, RECEIVED) == "topilmadi"
