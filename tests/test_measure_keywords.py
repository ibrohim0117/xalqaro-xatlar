"""scripts/measure_keywords.py testi — to'qilgan jumlalar bilan."""

from scripts.measure_keywords import keywords_in


def test_keywords_found_in_russian_and_uzbek():
    text = "Нотариус просит сообщить о наследственном деле; Meros ishi bo'yicha"
    assert {"нотари…", "наследств…", "meros / мерос"} <= keywords_in(text)


def test_keywords_ignore_case_and_unrelated_text():
    assert keywords_in("НОТАРИАЛЬНАЯ КОНТОРА") >= {"нотари…"}
    assert keywords_in("Просим вручить документы") == {"вруч…"}  # вручить, вручение
    assert keywords_in("истребовать свидетельство") == {"истребов…", "свидетельств…"}
    assert keywords_in("Ферганская область") == set()
