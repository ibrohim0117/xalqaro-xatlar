"""src/engine/predict.py testlari — soxta json'lar va to'qilgan nomlar bilan."""

from src.engine.model import (
    Model,
    learn_model,
    load_model,
    number_template,
    save_model,
    template_matches,
)
from src.engine.predict import predict
from src.evaluation.evaluate import field_values
from src.fields.number_template import Template
from src.reading.pages import CachedPage
from src.reading.pdf_text import PageText, Word

FARGONA = "Farg'ona viloyati adliya boshqarmasi"  # shablonga mos
ANDIJON = "Andijon viloyat adliya bo'limi (soxta)"  # shablonga mos emas
NOTARIAT = "Notariat boshqarmasi (soxta)"


def truth(boshqarma: str, summary: str = "Standart mazmun", sender: str | None = None) -> dict:
    if "notariat" in boshqarma.lower():
        task = {
            "asosiy_ijrochilar": ["SOXTA XODIM"],
            "asosiy_ijrochilar_boshqarmalari": [boshqarma],
        }
    else:
        task = {"asosiy_ijrochilar": [boshqarma], "asosiy_ijrochilar_boshqarmalari": []}
    doc = {"hujjatning_qisqacha_mazmuni": summary, "hujjat_junatuvchi_tashkilot": sender}
    return {"rekvizit_document": doc, "tasks": [task]}


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
    assert boshqarma_of(answer) == [FARGONA] and "boshqarma" not in answer["tekshirish_kerak"]
    answer = predict(pages_of("Нотариус, наследственное дело. Андижанская область"), MODEL)
    assert boshqarma_of(answer) == [NOTARIAT]  # notariat hududdan ustun


def test_unknown_region_gets_template_name_and_flag():
    answer = predict(pages_of("Бухарская область"), MODEL)
    assert boshqarma_of(answer) == ["Buxoro viloyati adliya boshqarmasi"]
    assert "boshqarma" in answer["tekshirish_kerak"]


def test_nothing_found_means_empty_and_flag():
    answer = predict(pages_of("Просим оказать правовую помощь"), MODEL)
    assert boshqarma_of(answer) == [] and "boshqarma" in answer["tekshirish_kerak"]


def test_answer_is_readable_by_evaluate():
    answer = predict(pages_of("Ферганская область"), MODEL)
    values = field_values(answer, truth(FARGONA))
    assert values["boshqarma"] == (FARGONA, FARGONA)
    assert values["hujjatning_qisqacha_mazmuni"] == ("Standart mazmun", "Standart mazmun")


def test_model_learns_number_template_per_sender():
    numbered = [truth(FARGONA, sender="Rossiya"), truth(FARGONA, sender="rossiya ")]
    numbered[0]["rekvizit_document"]["hujjat_raqami"] = "54/07-17001/25"
    numbered[1]["rekvizit_document"]["hujjat_raqami"] = "54/07-9912/25"
    model = learn_model([*numbered, truth(NOTARIAT, sender="Belarus")])
    assert number_template(model, "Rossiya") == Template("9/9-9/9", "54/07-")
    assert number_template(model, "Belarus") is None  # bitta xatdan qolip o'rganilmaydi
    assert number_template(model, None) is None


def test_model_save_and_load(tmp_path):
    save_model(MODEL, tmp_path / "model.json")
    assert load_model(tmp_path / "model.json") == MODEL
    assert Model() == Model(names={}, summary=None)


# Jo'natuvchi: to'qilgan blanklar (sahifaning yuqori qismi), telefon raqami bilan
NOVO = "ГЛАВНОЕ УПРАВЛЕНИЕ МИНИСТЕРСТВА ЮСТИЦИИ ПО НОВОСИБИРСКОЙ ОБЛАСТИ тел. (383) 304-86-27"
GEORGIA = "Министерство юстиции Грузии Агентство развития государственных сервисов"
SENDER_MODEL = learn_model(
    [truth(FARGONA, sender="Soxta Novosibirsk"), truth(FARGONA, sender="Soxta Gruziya")],
    [NOVO, GEORGIA],
)


def letter_with_blank(blank: str) -> list[CachedPage]:
    """Blank sahifa tepasida (y=0.1), viloyat matni pastroqda."""
    words = [
        Word(t, 0.1 + 0.03 * i, 0.1, 0.13 + 0.03 * i, 0.11, 0) for i, t in enumerate(blank.split())
    ]
    words += [Word("Ферганская", 0.1, 0.5, 0.2, 0.51, 1), Word("область", 0.21, 0.5, 0.3, 0.51, 1)]
    return [CachedPage(1, PageText(1, "text_layer", words), None)]


def test_sender_model_stores_blank_words_only():
    assert SENDER_MODEL.sender_names == ["Soxta Novosibirsk", "Soxta Gruziya"]
    assert "новосибирской" in SENDER_MODEL.sender_texts[0]
    assert not any(ch.isdigit() for ch in SENDER_MODEL.sender_texts[0])  # telefon saqlanmadi


def test_predict_finds_familiar_sender():
    answer = predict(letter_with_blank(NOVO), SENDER_MODEL)  # shu tashkilotdan yana xat
    assert answer["rekvizit_document"]["hujjat_junatuvchi_tashkilot"] == "Soxta Novosibirsk"
    assert "hujjat_junatuvchi_tashkilot" not in answer["tekshirish_kerak"]


def test_unknown_sender_is_flagged_not_guessed():
    blank = "Министерство юстиции Республики Молдова Агентство публичных услуг"
    answer = predict(letter_with_blank(blank), SENDER_MODEL)
    assert answer["rekvizit_document"]["hujjat_junatuvchi_tashkilot"] is None
    assert "hujjat_junatuvchi_tashkilot" in answer["tekshirish_kerak"]
    # o'rniga xodimga o'zbekcha variantlar taklif qilinadi
    assert (
        "Moldova Respublikasi Davlat xizmatlari agentligi"
        in (answer["takliflar"]["hujjat_junatuvchi_tashkilot"])
    )


def test_predict_signer_from_letter_end():
    words = [
        Word("Ферганская", 0.1, 0.3, 0.2, 0.31, 0),
        Word("область", 0.21, 0.3, 0.3, 0.31, 0),
        Word("Начальник", 0.1, 0.8, 0.2, 0.81, 1),
        Word("А.Б.", 0.7, 0.8, 0.74, 0.81, 1),
        Word("Сидоров", 0.75, 0.8, 0.85, 0.81, 1),
    ]
    pages = [CachedPage(1, PageText(1, "text_layer", words), None)]
    answer = predict(pages, MODEL)
    assert answer["rekvizit_document"]["imzolagan_shaxs"] == "A.B.Sidorov"
    assert "imzolagan_shaxs" not in answer["tekshirish_kerak"]


def test_missing_signer_is_flagged():
    answer = predict(pages_of("Ферганская область"), MODEL)
    assert answer["rekvizit_document"]["imzolagan_shaxs"] is None
    assert "imzolagan_shaxs" in answer["tekshirish_kerak"]


def test_date_is_filled_and_number_only_suggested():
    words = [
        Word("05.12.2025", 0.1, 0.3, 0.2, 0.31, 0),
        Word("№", 0.3, 0.3, 0.32, 0.31, 0),
        Word("54/07-16606", 0.33, 0.3, 0.45, 0.31, 0),
        Word("Ферганская", 0.1, 0.5, 0.2, 0.51, 1),
        Word("область", 0.21, 0.5, 0.3, 0.51, 1),
    ]
    answer = predict([CachedPage(1, PageText(1, "text_layer", words), None)], MODEL)
    assert answer["rekvizit_document"]["hujjat_sana"] == "05.12.2025"  # matn qatlamidan
    assert answer["rekvizit_document"]["hujjat_raqami"] is None  # raqam avtomatik yozilmaydi
    assert answer["takliflar"] == {"hujjat_raqami": "54/07-16606"}
    assert "hujjat_raqami" in answer["tekshirish_kerak"]
    assert "hujjat_sana" not in answer["tekshirish_kerak"]


def test_ocr_only_date_is_a_suggestion():
    words = [Word("05.12.2025", 0.1, 0.3, 0.2, 0.31, 0), Word("№", 0.3, 0.3, 0.32, 0.31, 0)]
    page = CachedPage(1, PageText(1, "text_layer", []), PageText(1, "ocr", words))
    answer = predict([page], MODEL)
    assert answer["rekvizit_document"]["hujjat_sana"] is None
    assert answer["takliflar"] == {"hujjat_sana": "05.12.2025"}
    assert "hujjat_sana" in answer["tekshirish_kerak"]
