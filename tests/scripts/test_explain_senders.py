"""Matcher.ranked testi (explain_senders va predict shuni ishlatadi) — to'qilgan blanklar bilan."""

from src.fields.sender import Matcher

NOVO = "ГЛАВНОЕ УПРАВЛЕНИЕ МИНИСТЕРСТВА ЮСТИЦИИ ПО НОВОСИБИРСКОЙ ОБЛАСТИ"
GEORGIA = "Министерство юстиции Грузии Агентство развития государственных сервисов"


def test_ranked_gives_one_score_per_sender():
    matcher = Matcher([NOVO, NOVO + " отдел", GEORGIA], ["Novosibirsk", "novosibirsk ", "Gruziya"])
    scores = matcher.ranked(NOVO)
    assert [name for _, name in scores] == ["Novosibirsk", "Gruziya"]  # tashkilotga bitta ball
    assert scores[0][0] > scores[1][0]
