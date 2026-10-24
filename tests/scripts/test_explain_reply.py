"""scripts/rekvizit/explain_reply.py testlari — to'qilgan matn bilan."""

from scripts.rekvizit.explain_reply import keywords_before, occurrence
from src.fields.number_template import key

TEXT = " ".join(
    [
        "По делу № 2-345/2025 на Ваш запрос № 77 от 01.02.2025 сообщаем, в ответ на письмо",
        "Министерства юстиции Республики Узбекистан от 05.06.2025 № 17/08-10/ 2934",
    ]
).split()
OURS = key("17/08-10/2934")


def test_occurrence_finds_split_number():
    i = occurrence(TEXT, OURS)
    assert TEXT[i] == "17/08-10/"  # raqam ikki so'zga bo'lingan — boshlanishi
    assert occurrence(TEXT, key("99/99")) is None


def test_keywords_before_our_number():
    expected = {"в ответ", "министерств", "юстиции", "узбекистан", "письм"}
    assert expected <= keywords_before(TEXT, occurrence(TEXT, OURS))
