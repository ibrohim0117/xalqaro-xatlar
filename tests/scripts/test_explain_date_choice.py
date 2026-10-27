"""scripts/ocr/explain_date_choice.py testlari — to'qilgan so'zlar bilan, qiymatlar chiqmasligi."""

from scripts.ocr.explain_date_choice import anchor_candidates, verdict
from src.reading.pdf_text import Word


def test_verdict_tells_the_relation_without_the_value():
    truth = "17.01.2026"
    assert verdict("17.01.2026", truth) == "to'g'ri"
    assert verdict("17.01.2025", truth) == "yil farq"
    assert verdict("18.02.2026", truth) == "kun va oy farq"
    assert verdict("05.11.2024", truth) == "boshqa sana"
    assert verdict(None, truth) == "—"
    assert verdict("17.01.2026", None) == "json'da sana yo'q"


def word(text: str, x: float, y: float, line: int) -> Word:
    return Word(text, x, y, x + 0.1, y + 0.02, line)


def test_anchor_candidates_show_where_each_number_sign_is_and_which_one_wins():
    words = [
        # blank qatori: o'rtada logotip — OCR uni "N°" deb o'qigan (to'qilgan holat)
        word("ПРЕЗИДЕНТИНИН", 0.15, 0.10, 0),
        word("N°", 0.50, 0.10, 0),
        word("УЧРЕЖДЕНИЕ", 0.60, 0.10, 0),
        # bank rekviziti
        word("б/с", 0.15, 0.18, 1),
        word("№", 0.20, 0.18, 1),
        word("1234567890123", 0.24, 0.18, 1),
        # haqiqiy sana-raqam qatori: sana va raqam qo'lda (matnda faqat chiziqlar)
        word("_____", 0.10, 0.30, 2),
        word("№", 0.30, 0.30, 2),
        word("_____", 0.34, 0.30, 2),
    ]
    rows = anchor_candidates(words)
    assert [status for _, status, _, _ in rows] == [
        "TANLANDI",  # eng tepadagisi — hozirgi qoida
        "bank rekviziti",
        "nomzod (pastroqda)",
    ]
    logo, real = rows[0], rows[2]
    assert (logo[2], logo[3]) == ("КК", "КК")  # yonida oddiy so'zlar — faqat tuzilishi
    assert real[2] == real[3] == "__"
    assert "ПРЕЗИДЕНТИНИН" not in repr(rows) and "1234567890123" not in repr(rows)
