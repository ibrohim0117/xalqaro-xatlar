"""explain_first_letters testlari — to'qilgan nomlar bilan."""

from scripts.rekvizit.explain_first_letters import best_match, bucket


def test_best_match_and_bucket():
    options = ["Soxta viloyati FHDY bo'limi", None, "Soxta Adliya vazirligi"]
    similarity, best = best_match("soxta viloyati FHDY boshqarmasi", options)
    assert best == "Soxta viloyati FHDY bo'limi" and 0.75 <= similarity < 1
    assert best_match("Soxta", []) == (0.0, None)
    assert bucket(0.95) == ">= 0.90" and bucket(0.8) == "0.75–0.90" and bucket(0.1) == "< 0.75"
