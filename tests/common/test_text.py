"""src/common/text.py testlari."""

import pytest

from src.common.text import most_common, normalize, to_latin


def test_normalize_ignores_harmless_differences():
    assert normalize("O.N. Xrushev", spaceless=True) == normalize("O.N.Xrushev", spaceless=True)
    assert normalize("54/07–16606") == normalize("54/07-16606")  # uzun chiziq
    assert normalize("Bo‘yicha") == normalize("Bo'yicha")  # apostrof turi
    assert normalize("  Xalqaro  huquqiy yordam. ") == "xalqaro huquqiy yordam"
    assert normalize(None) == ""


def test_normalize_keeps_real_differences():
    assert normalize("Toshkent shahri") != normalize("Toshkent viloyati")
    assert normalize("01.10.2026", spaceless=True) != normalize("10.01.2026", spaceless=True)


def test_most_common_counts_harmless_variants_together():
    names = ["A.B. Soxtayev", "A.B.Soxtayev", "V.G. Boshqayev"]
    assert most_common(names, spaceless=True) == ("A.B. Soxtayev", 2)
    assert most_common([None, ""]) == (None, 0)


@pytest.mark.parametrize(
    ("cyrillic", "latin"),
    [
        ("Хрущев", "Xrushev"),  # Х -> X, Щ -> Sh
        ("Сидоров", "Sidorov"),
        ("Чайковская", "Chaykovskaya"),  # Ч -> Ch, Й -> Y, Я -> Ya
        ("Евгений", "Yevgeniy"),  # so'z boshidagi Е -> Ye
        ("Цой", "Tsoy"),
        ("Шарипов", "Sharipov"),
        ("Ўринов", "O'rinov"),  # o'zbek kirill harflari
        ("Қодиров", "Qodirov"),
    ],
)
def test_to_latin(cyrillic, latin):
    assert to_latin(cyrillic) == latin


def test_latin_letters_only_changes_cyrillic_letters():
    from src.common.text import latin_letters

    assert latin_letters("12-И/34") == "12-I/34"
    assert latin_letters("54/07-16606") == "54/07-16606"  # harfsiz — o'zgarmaydi
    assert latin_letters("Ен-5 і") == "En-5 i"  # "Е" doim "E"; ukraincha "і" ham
    assert latin_letters("AB-1") == "AB-1"  # lotin harflar o'zgarmaydi
