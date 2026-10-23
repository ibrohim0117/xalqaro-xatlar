"""src/predict.py testlari — soxta json'lar va to'qilgan nomlar bilan."""

from src.evaluate import field_values
from src.pdf_text import PageText, Word
from src.predict import Model, learn_model, load_model, predict, save_model, template_matches
from src.text_cache import CachedPage

FARGONA = "Farg'ona viloyati adliya boshqarmasi"  # shablonga mos
ANDIJON = "Andijon viloyat adliya bo'limi (soxta)"  # shablonga mos emas
NOTARIAT = "Notariat boshqarmasi (soxta)"


def truth(boshqarma: str, summary: str = "Standart mazmun") -> dict:
    if "notariat" in boshqarma.lower():
        task = {
            "asosiy_ijrochilar": ["SOXTA XODIM"],
            "asosiy_ijrochilar_boshqarmalari": [boshqarma],
        }
    else:
        task = {"asosiy_ijrochilar": [boshqarma], "asosiy_ijrochilar_boshqarmalari": []}
    return {"rekvizit_document": {"hujjatning_qisqacha_mazmuni": summary}, "tasks": [task]}


def pages_of(text: str) -> list[CachedPage]:
    words = [Word(token, 0.1, 0.5, 0.2, 0.51, 0) for token in text.split()]
    return [CachedPage(1, PageText(1, "text_layer", words), None)]


def boshqarma_of(answer: dict) -> list[str]:
    return answer["tasks"][0]["asosiy_ijrochilar_boshqarmalari"]


MODEL = learn_model(
    [truth(FARGONA), truth(FARGONA), truth(ANDIJON, "Boshqa mazmun"), truth(NOTARIAT)]
)


def test_learn_model_from_dev_truths():
    assert MODEL.names == {"fargona": FARGONA, "andijon": ANDIJON, "notariat": NOTARIAT}
    assert MODEL.summary == "Standart mazmun"  # 3 ta xatdan 1 tasi boshqacha
    assert template_matches(MODEL) == (1, 2)  # Farg'ona mos, Andijon emas; notariat sanalmaydi


def test_predict_uses_learned_names():
    answer = predict(pages_of("Ферганская область, Кокандский район"), MODEL)
    assert boshqarma_of(answer) == [FARGONA] and answer["tekshirish_kerak"] == []
    answer = predict(pages_of("Нотариус, наследственное дело. Андижанская область"), MODEL)
    assert boshqarma_of(answer) == [NOTARIAT]  # notariat hududdan ustun


def test_unknown_region_gets_template_name_and_flag():
    answer = predict(pages_of("Бухарская область"), MODEL)
    assert boshqarma_of(answer) == ["Buxoro viloyati adliya boshqarmasi"]
    assert answer["tekshirish_kerak"] == ["boshqarma"]


def test_nothing_found_means_empty_and_flag():
    answer = predict(pages_of("Просим оказать правовую помощь"), MODEL)
    assert boshqarma_of(answer) == [] and answer["tekshirish_kerak"] == ["boshqarma"]


def test_answer_is_readable_by_evaluate():
    answer = predict(pages_of("Ферганская область"), MODEL)
    values = field_values(answer, truth(FARGONA))
    assert values["boshqarma"] == (FARGONA, FARGONA)
    assert values["hujjatning_qisqacha_mazmuni"] == ("Standart mazmun", "Standart mazmun")


def test_model_save_and_load(tmp_path):
    save_model(MODEL, tmp_path / "model.json")
    assert load_model(tmp_path / "model.json") == MODEL
    assert Model() == Model(names={}, summary=None)
