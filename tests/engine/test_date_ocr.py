"""src/engine/date_ocr.py testlari — soxta OCR'lar bilan (haqiqiy model kerak emas)."""

import time
from datetime import date

import pymupdf
import pytest

from src.engine.date_ocr import DateOcr, DateReading, apply_reading, build_date_ocr
from tests.conftest import FAKE_LETTER, make_letter_pdf
from tests.engine.test_locate import pages_of

RECEIVED = date(2026, 4, 1)
NO_PRINTED_DATE = [  # sana qo'lda yozilgan — matn qatlamida faqat "№" va raqam
    line if "№" not in line[2] else (line[0], line[1], "№ 55/07-1234") for line in FAKE_LETTER
]


class FakeReader:
    """Har bo'lakka bir xil matn qaytaradi; kerak bo'lsa — ishlamay qoladi."""

    def __init__(self, name: str, text: str = "", broken: bool = False):
        self.name, self.text, self.broken, self.calls = name, text, broken, 0

    def read(self, png: bytes) -> str:
        self.calls += 1
        if self.broken:
            raise ConnectionError("server o'chiq")
        return self.text


@pytest.fixture
def letter(tmp_path):
    def make(lines):
        pdf = make_letter_pdf(tmp_path / "xat.pdf", lines)
        return pymupdf.open(pdf)[0], pages_of(pdf)[0]

    return make


def test_printed_date_is_automatic_and_ocr_reads_for_the_number(letter):
    vlm = FakeReader("vlm", "01.01.2026 № 55/07-1234")
    reading = DateOcr([vlm]).read(*letter(FAKE_LETTER), RECEIVED)
    assert reading.auto == "12.03.2026" and reading.prefill is None
    assert reading.suggestions == []  # sana bosma — OCR sanasi taklif qilinmaydi
    assert vlm.calls > 0 and "vlm" in reading.texts  # B5.12: OCR matni raqam uchun


def test_vlm_confirmed_by_another_ocr_is_prefilled(letter):
    readers = [FakeReader("vlm", "12.03.2026 № 55/07"), FakeReader("rapid", "12.03.2026 No 55")]
    reading = DateOcr(readers).read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert reading.auto is None
    assert reading.prefill == "12.03.2026"  # "tekshiring" belgisi bilan yoziladi
    assert reading.suggestions == ["12.03.2026"]
    assert reading.readers == ["vlm", "rapid"]


def test_disagreement_gives_only_suggestions(letter):
    readers = [FakeReader("vlm", "12.03.2026"), FakeReader("rapid", "13.03.2026")]
    reading = DateOcr(readers).read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert reading.prefill is None
    assert set(reading.suggestions) == {"12.03.2026", "13.03.2026"}


def test_misread_year_is_fixed_into_the_window(letter):
    # B5.11: kun va oy o'sha, yil — oynaga tushadigani; baribir "tekshiring" bilan (prefill)
    readers = [FakeReader("vlm", "12.03.2015"), FakeReader("rapid", "12.03.2015")]
    reading = DateOcr(readers).read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert reading.prefill == "12.03.2026" and reading.auto is None


def test_broken_vlm_falls_back_to_vote(letter):
    readers = [
        FakeReader("vlm", broken=True),
        FakeReader("rapid", "12.03.2026"),
        FakeReader("tesseract", "12.03.2026"),
    ]
    reading = DateOcr(readers).read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert reading.readers == ["rapid", "tesseract"]  # VLM chetlandi
    assert reading.prefill == "12.03.2026"  # ikki OCR kelishdi (oddiy ovoz)


def test_vlm_extract_reads_its_own_crops_and_needs_confirmation(letter):
    extract = FakeReader("vlm-extract", '{"sana": "12.03.2026", "raqam": "55/07-1234"}')
    rapid = FakeReader("rapid", "12.03.2026 No 55")
    reading = DateOcr([extract, rapid]).read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert extract.calls == 3  # header, page, line
    assert set(reading.texts["vlm-extract"]) == {"header", "page", "line"}  # raqam uchun saqlanadi
    assert rapid.calls == 3  # date, line, header ("number" va "page" o'qilmaydi)
    assert reading.prefill == "12.03.2026"
    # header va page'da bir xil sana — o'zini o'zi tasdiqlash hisob emas: yozilmaydi, faqat taklif
    alone = DateOcr([FakeReader("vlm-extract", '{"sana": "12.03.2026"}')])
    reading = alone.read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert reading.prefill is None and reading.suggestions == ["12.03.2026"]


def test_broken_vlm_extract_leaves_the_old_vlm_as_finder(letter):
    readers = [
        FakeReader("vlm-extract", broken=True),
        FakeReader("vlm", "12.03.2026 № 55/07"),
        FakeReader("rapid", "12.03.2026 No 55"),
    ]
    reading = DateOcr(readers).read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert reading.readers == ["vlm", "rapid"]
    assert reading.prefill == "12.03.2026"  # VLM ko'chirish topdi, RapidOCR tasdiqladi


class SlowReader(FakeReader):
    """Har bo'lakda biroz kutadi va qachon o'qiganini yozib boradi — parallel ishlashni ko'rish."""

    def __init__(self, name: str, text: str = "", delay: float = 0.05):
        super().__init__(name, text)
        self.delay, self.spans = delay, []

    def read(self, png: bytes) -> str:
        start = time.perf_counter()
        time.sleep(self.delay)
        self.spans.append((start, time.perf_counter()))
        return super().read(png)


def overlap(a: SlowReader, b: SlowReader) -> bool:
    return any(s1 < e2 and s2 < e1 for s1, e1 in a.spans for s2, e2 in b.spans)


def test_cpu_ocrs_work_while_waiting_for_vlm_but_vlm_gets_one_request_at_a_time(letter):
    extract = SlowReader("vlm-extract", '{"sana": "12.03.2026"}', delay=0.08)
    vlm = SlowReader("vlm", "12.03.2026 № 55/07", delay=0.08)
    rapid = SlowReader("rapidocr", "12.03.2026 No 55", delay=0.01)  # tez — oldinroq tugaydi
    tess = SlowReader("tesseract-block", "№ 55", delay=0.01)
    reading = DateOcr([extract, vlm, rapid, tess]).read(*letter(NO_PRINTED_DATE), RECEIVED)
    assert overlap(extract, rapid)  # protsessor OCR'i VLM javobini kutish ichida ishladi
    assert not overlap(extract, vlm)  # VLM serveriga bir vaqtda bitta so'rov (8 GB xotira)
    assert not overlap(rapid, tess)  # protsessor yo'lagi ichida ham ketma-ket
    # kim avval tugaganidan qat'i nazar, natija tartibi o'sha: 1-ishlagan OCR — topuvchi
    assert reading.readers == ["vlm-extract", "vlm", "rapidocr", "tesseract-block"]
    assert reading.prefill == "12.03.2026"


def test_parallel_reading_gives_the_same_result_as_one_lane(letter, monkeypatch):
    def run():
        readers = [
            FakeReader("vlm-extract", '{"sana": "12.03.2026", "raqam": "55/07-1234"}'),
            FakeReader("vlm", broken=True),
            FakeReader("rapidocr", "12.08.2026 No 55"),
            FakeReader("tesseract-block", "12.03.2026"),
        ]
        reading = DateOcr(readers).read(*letter(NO_PRINTED_DATE), RECEIVED)
        return reading.prefill, reading.suggestions, reading.readers, reading.texts

    parallel = run()
    monkeypatch.setattr("src.engine.date_ocr.lane_of", lambda name: "bitta")  # eskicha: navbat
    assert parallel == run()
    assert parallel[2] == ["vlm-extract", "rapidocr", "tesseract-block"]  # ishlamagani chetda


def wait_for(condition, seconds: float = 5.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)


def test_vlm_reads_header_and_page_before_page_ocr_and_waits_for_the_anchor(letter):
    page, first = letter(NO_PRINTED_DATE)
    extract = FakeReader("vlm-extract", '{"sana": "12.03.2026"}')
    vlm = FakeReader("vlm", "12.03.2026 № 55/07")
    rapid = FakeReader("rapidocr", "12.03.2026 No 55")
    ocr = DateOcr([extract, vlm, rapid])
    early = ocr.start(page)  # pipeline buni sahifa OCR'idan OLDIN chaqiradi
    wait_for(lambda: extract.calls == 2)
    time.sleep(0.05)  # "№" qatori hali yo'q — navbat shu yerda kutib turadi
    assert (extract.calls, vlm.calls, rapid.calls) == (2, 0, 0)  # faqat header va page o'qildi
    reading = ocr.read(page, first, RECEIVED, early)
    assert (extract.calls, vlm.calls, rapid.calls) == (3, 3, 3)
    assert list(reading.texts["vlm-extract"]) == ["header", "page", "line"]  # tartib o'sha
    assert list(reading.texts["vlm"]) == ["header", "line", "date"]
    assert reading.readers == ["vlm-extract", "vlm", "rapidocr"]


def test_abandoned_early_reading_stops_instead_of_waiting_forever(letter):
    page, _ = letter(NO_PRINTED_DATE)
    extract, vlm = FakeReader("vlm-extract", "x"), FakeReader("vlm", "y")
    early = DateOcr([extract, vlm]).start(page)
    early.abandon()  # zanjir xato bilan to'xtadi — "№" qatori hech qachon kelmaydi
    early.job.result(timeout=5)  # osilib qolmaydi
    assert (extract.calls, vlm.calls) == (2, 0)  # header va page'dan nariga o'tmadi


def test_early_start_gives_the_same_result_as_one_lane(letter, monkeypatch):
    def run():
        readers = [
            FakeReader("vlm-extract", '{"sana": "12.03.2026", "raqam": "55/07-1234"}'),
            FakeReader("vlm", "12.03.2026 № 55/07-1234"),
            FakeReader("rapidocr", "12.08.2026 No 55"),
        ]
        ocr = DateOcr(readers)
        page, first = letter(NO_PRINTED_DATE)
        reading = ocr.read(page, first, RECEIVED, ocr.start(page))
        return reading.prefill, reading.suggestions, reading.readers, reading.texts

    early = run()
    monkeypatch.setattr("src.engine.date_ocr.lane_of", lambda name: "bitta")  # eskicha: navbat
    assert early == run()


def answer_with(date_value=None, flags=("hujjat_sana", "hujjat_raqami")):
    return {
        "rekvizit_document": {"hujjat_sana": date_value},
        "tekshirish_kerak": list(flags),
        "takliflar": {"hujjat_sana": "01.01.2026"},
    }


def test_apply_prefill_keeps_the_flag():
    answer = answer_with()
    apply_reading(answer, DateReading(prefill="12.03.2026", suggestions=["12.03.2026"]))
    assert answer["rekvizit_document"]["hujjat_sana"] == "12.03.2026"
    assert "hujjat_sana" in answer["tekshirish_kerak"]
    assert answer["takliflar"]["hujjat_sana"] == ["12.03.2026"]  # bitta taklif o'rniga ro'yxat


def test_apply_auto_removes_the_flag_and_nothing_keeps_old_values():
    answer = answer_with()
    apply_reading(answer, DateReading(auto="12.03.2026"))
    assert "hujjat_sana" not in answer["tekshirish_kerak"]
    answer = answer_with()
    apply_reading(answer, DateReading())  # OCR hech narsa topmadi
    assert answer["rekvizit_document"]["hujjat_sana"] is None
    assert answer["takliflar"]["hujjat_sana"] == "01.01.2026"  # predict taklifi qoladi


def test_build_without_readers_is_off():
    assert build_date_ocr("") is None
    assert build_date_ocr("yoq-ocr") is None  # noma'lum nom — ogohlantirish bilan chetlanadi
