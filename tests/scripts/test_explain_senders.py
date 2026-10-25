"""Matcher.ranked testi (explain_senders va predict shuni ishlatadi) — to'qilgan blanklar bilan."""

from src.fields.sender import Matcher

NOVO = "ГЛАВНОЕ УПРАВЛЕНИЕ МИНИСТЕРСТВА ЮСТИЦИИ ПО НОВОСИБИРСКОЙ ОБЛАСТИ"
GEORGIA = "Министерство юстиции Грузии Агентство развития государственных сервисов"


def test_ranked_gives_one_score_per_sender():
    matcher = Matcher([NOVO, NOVO + " отдел", GEORGIA], ["Novosibirsk", "novosibirsk ", "Gruziya"])
    scores = matcher.ranked(NOVO)
    assert [name for _, name in scores] == ["Novosibirsk", "Gruziya"]  # tashkilotga bitta ball
    assert scores[0][0] > scores[1][0]


def test_family_and_skeleton_hide_place_names():
    from scripts.rekvizit.explain_senders import family, skeleton

    assert family("Soxta viloyati FHDY bo'limi") == "FHDY bo'limi"
    gu = "Rossiya Federatsiyasi Adliya vazirligining Soxta viloyati bo'yicha bosh boshqarmasi"
    assert family(gu) == "adliya bosh boshqarmasi"
    assert family("Moldova Respublikasi Adliya vazirligi") == "vazirlik"
    assert family("Soxta shahar sudi") == "boshqa"
    assert skeleton("Soxta Noma'lum viloyati FHDY bo'limi") == "… viloyati fhdy bo'limi"


def test_place_pick_takes_first_known_sender_with_the_blank_place():
    from scripts.rekvizit.explain_senders import place_pick

    ranking = [(0.40, "Gruziya Adliya vazirligi"), (0.35, "Moldova Respublikasi Adliya vazirligi")]
    assert place_pick(ranking, ["Moldova"], 0.0) == "moldova respublikasi adliya vazirligi"
    assert place_pick(ranking, ["Moldova"], 0.38) is None  # ball pastroq — olinmaydi
    assert place_pick(ranking, [], 0.0) is None  # blankda joy yo'q — ehtiyot
