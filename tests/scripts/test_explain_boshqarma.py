"""scripts/boshqarma/explain_errors.py testlari — to'qilgan nomlar bilan."""

from scripts.boshqarma.explain_errors import kind_of

FARGONA = "Farg'ona viloyati adliya boshqarmasi"
NOTARIAT = "Notariat, advokatura va mediatsiya boshqarmasi"
XALQARO = "Xalqaro-huquqiy hamkorlik boshqarmasi"


def test_error_kinds():
    assert kind_of(FARGONA, FARGONA, set()) == "to'g'ri"
    assert kind_of(FARGONA, None, set()) == "javob yo'q: hudud topilmadi"
    assert kind_of(XALQARO, None, set()) == "javob yo'q: xalqaro"
    assert kind_of(FARGONA, NOTARIAT, set()) == "guruh xato: viloyat -> notariat"
    andijon = "Andijon viloyati adliya boshqarmasi"
    in_list = "hudud xato: to'g'risi nomzodlarda bor"
    assert kind_of(FARGONA, andijon, {"fargona", "andijon"}) == in_list
    assert kind_of(FARGONA, andijon, {"andijon"}) == "hudud xato"
    other_name = "Farg'ona viloyat adliya boshqarmasi"
    assert kind_of(FARGONA, other_name, set()) == "nom farq (hudud to'g'ri)"
