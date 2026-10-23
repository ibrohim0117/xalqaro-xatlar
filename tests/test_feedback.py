"""src/feedback.py testlari — to'qilgan blank va nomlar bilan."""

from src.feedback import confirm_sender, load_confirmed, with_confirmed
from src.predict import Model, predict
from tests.test_predict import letter_with_blank

ARGENTINA = "Ministerio de Justicia de la República Argentina tel. +54 11 1234-5678"


def test_confirm_and_load(tmp_path):
    path = tmp_path / "feedback.jsonl"
    assert load_confirmed(path) == ([], [])
    confirm_sender(ARGENTINA, "Argentina Respublikasi Adliya vazirligi", path)
    blanks, names = load_confirmed(path)
    assert names == ["Argentina Respublikasi Adliya vazirligi"]
    assert "argentina" in blanks[0] and not any(ch.isdigit() for ch in blanks[0])  # telefon yo'q


def test_confirmed_sender_is_recognized_next_time(tmp_path):
    path = tmp_path / "feedback.jsonl"
    model = Model(names={"fargona": "Farg'ona viloyati adliya boshqarmasi"}, summary="Mazmun")
    first = predict(letter_with_blank(ARGENTINA), model)
    assert first["rekvizit_document"]["hujjat_junatuvchi_tashkilot"] is None  # 1-marta: notanish

    confirm_sender(ARGENTINA, "Argentina Respublikasi Adliya vazirligi", path)  # xodim tasdiqladi
    model = with_confirmed(model, *load_confirmed(path))
    second = predict(letter_with_blank(ARGENTINA), model)
    sender = second["rekvizit_document"]["hujjat_junatuvchi_tashkilot"]
    assert sender == "Argentina Respublikasi Adliya vazirligi"  # 2-marta: avtomatik
