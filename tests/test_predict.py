"""src/predict.py testlari — soxta json'lar va to'qilgan nomlar bilan."""

from src.evaluate import field_values
from src.pdf_text import PageText, Word
from src.predict import Model, learn_model, load_model, predict, save_model, template_matches
from src.text_cache import CachedPage

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


def test_model_save_and_load(tmp_path):
    save_model(MODEL, tmp_path / "model.json")
    assert load_model(tmp_path / "model.json") == MODEL
    assert Model() == Model(names={}, summary=None)


# Jo'natuvchi: har tashkilotdan 2 tadan to'qilgan xat (filtr "kamida 2 xatda" bo'lgani uchun)
NOVO = "Главное управление Министерства юстиции России по Новосибирской области направляет"
GEORGIA = "Министерство юстиции Грузии Агентство развития государственных сервисов просит"
SENDER_MODEL = learn_model(
    [truth(FARGONA, sender="Soxta Novosibirsk")] * 2 + [truth(FARGONA, sender="Soxta Gruziya")] * 2,
    [NOVO + " Каримову", NOVO + " Сидорову", GEORGIA + " Алиеву", GEORGIA + " Петрову"],
)


def test_sender_model_stores_only_shared_words():
    assert SENDER_MODEL.sender_names == ["Soxta Novosibirsk"] * 2 + ["Soxta Gruziya"] * 2
    assert "новосибирской" in SENDER_MODEL.sender_texts[0]
    assert not any("каримову" in text for text in SENDER_MODEL.sender_texts)  # ism saqlanmadi


def test_predict_finds_familiar_sender():
    text = "ГУ Минюста России по Новосибирской области, Ферганская область"
    answer = predict(pages_of(text), SENDER_MODEL)
    assert answer["rekvizit_document"]["hujjat_junatuvchi_tashkilot"] == "Soxta Novosibirsk"
    assert "hujjat_junatuvchi_tashkilot" not in answer["tekshirish_kerak"]


def test_unknown_sender_is_flagged_not_guessed():
    answer = predict(pages_of("Министерство юстиции Республики Молдова просит"), SENDER_MODEL)
    assert answer["rekvizit_document"]["hujjat_junatuvchi_tashkilot"] is None
    assert "hujjat_junatuvchi_tashkilot" in answer["tekshirish_kerak"]


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
