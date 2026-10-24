"""scripts/ocr/date_failures.py testlari — to'qilgan OCR matnlari bilan."""

from datetime import date

from scripts.ocr.date_failures import outcome

RECEIVED, TRUTH = date(2026, 1, 9), "19.12.2025"


def test_outcomes_follow_the_prototype_rule():
    extract_ok = {"header": '{"sana": "19.12.2025", "raqam": "54"}'}  # aniq savol (vlm-extract)
    rapid_ok = {"line": "19.12.2025 № 54"}
    assert outcome([{}, {}], "19.12.2025", TRUTH, RECEIVED) == "yozildi to'g'ri"  # matn qatlami
    assert outcome([extract_ok, rapid_ok], None, TRUTH, RECEIVED) == "yozildi to'g'ri"  # + tasdiq
    wrong = {"header": "09.12.2025", "date": "09.12.2025"}
    assert outcome([wrong, wrong], None, TRUTH, RECEIVED) == "yozildi xato"
    other = {"date": "01.12.2025"}
    assert outcome([extract_ok, other], None, TRUTH, RECEIVED) == "faqat takliflarda"
    assert outcome([{"header": "№ 54"}, {}], None, TRUTH, RECEIVED) == "topilmadi"


def test_old_vlm_finder_takes_the_date_crop():
    vlm_ok, rapid_ok = {"date": "19.12.2025"}, {"line": "19.12.2025 № 54"}
    assert outcome([vlm_ok, rapid_ok], None, TRUTH, RECEIVED, finder="vlm") == "yozildi to'g'ri"
    assert outcome([vlm_ok, rapid_ok], None, TRUTH, RECEIVED) == "faqat takliflarda"  # header yo'q
