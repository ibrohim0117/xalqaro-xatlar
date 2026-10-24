"""src/fields/number_template.py testlari — to'qilgan raqamlar bilan."""

from src.fields.number_template import Template, fit, learn, matches, structure

SENDER = ["54/07-16606/25", "54/07-17001/25", "54/07-9912/25"]  # bitta tashkilotning raqamlari


def test_structure_hides_values_and_lengths():
    assert structure("54/07-16606/25") == structure("54/07-9912/25") == "9/9-9/9"
    assert structure("01-12/345-К") == "9-9/9-A"


def test_learn_structure_and_fixed_prefix():
    assert learn(SENDER) == Template("9/9-9/9", "54/07-")
    assert learn(SENDER[:1]) is None  # bitta xatdan qolip o'rganilmaydi
    assert learn(["54/07-16606", "12/345/6"]) is None  # aniq ko'pchilik tuzilish yo'q
    assert learn(["54/07-16606", "54/07-16606"]).prefix == ""  # takror xat: tartib raqami noma'lum
    assert learn(["54/07-16606", "55/01-17001"]).prefix == ""  # bosh qism doimiy emas


def test_fit_fixes_separators_and_prefix():
    template = learn(SENDER)
    assert fit("54/07/16606/25", template) == "54/07-16606/25"  # ajratgich turi
    assert fit("34/07-16606/25", template) == "54/07-16606/25"  # bosh qism
    assert fit("5407-16606/25", template) == "54/07-16606/25"  # bosh qismda ajratgich tushgan
    assert fit("54/0716606/25", template) == "54/07-16606/25"
    assert fit("54/07-16696/25", template) == "54/07-16696/25"  # qo'lda yozilgani — tuzatilmaydi
    assert fit("4/07-16606/25", template) == "4/07-16606/25"  # bosh qism uzunligi boshqa — tegmaydi
    assert fit("54/07-16606/25", template) == "54/07-16606/25"  # to'g'risi buzilmaydi


def test_matches_needs_structure_and_prefix():
    template = learn(SENDER)
    assert matches("54/07-12345/25", template)
    assert not matches("17/08-10/2934", template)  # boshqa raqam ("На №" yoki nusxa)
    assert not matches("55/07-12345/25", template)  # bosh qism boshqa
