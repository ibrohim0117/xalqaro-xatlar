"""src/baseline.py testlari — soxta qiymatlar bilan, real ma'lumotsiz."""

from src.baseline import learn, most_common, to_prediction
from src.evaluate import ALL_FIELDS, field_values

STANDART = "Soxta standart mazmun"


def fake_truth(mazmun: str, imzo: str) -> dict[str, str | None]:
    values = dict.fromkeys(ALL_FIELDS, "soxta")
    values["hujjatning_qisqacha_mazmuni"] = mazmun
    values["imzolagan_shaxs"] = imzo
    return values


def test_most_common_counts_harmless_variants_together():
    names = ["A.B. Soxtayev", "A.B.Soxtayev", "V.G. Boshqayev"]
    assert most_common(names, spaceless=True) == ("A.B. Soxtayev", 2)
    assert most_common([None, ""]) == (None, 0)


def test_learn_picks_majority_for_each_field():
    truths = [
        fake_truth(STANDART, "A.B.Soxtayev"),
        fake_truth(STANDART, "V.G.Boshqayev"),
        fake_truth("Boshqa mazmun", "V.G. Boshqayev"),
    ]
    guess, freq = learn(truths)
    assert guess["hujjatning_qisqacha_mazmuni"] == STANDART
    assert freq["hujjatning_qisqacha_mazmuni"] == 2
    assert guess["imzolagan_shaxs"] == "V.G.Boshqayev"  # bo'shliqli varianti ham sanaldi
    assert freq["imzolagan_shaxs"] == 2


def test_prediction_has_the_shape_evaluate_reads():
    guess = dict.fromkeys(ALL_FIELDS, "soxta")
    guess["boshqarma"] = "Soxta viloyati adliya boshqarmasi"
    truth = {"rekvizit_document": {}, "tasks": [{"asosiy_ijrochilar": []}]}
    pairs = field_values(to_prediction(guess), truth)
    assert {field: predicted for field, (predicted, _) in pairs.items()} == guess
