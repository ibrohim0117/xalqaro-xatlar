"""src/pdf_text.py testlari — faqat soxta xat bilan (tests/conftest.py)."""

from src.pdf_text import PageText, read_text_layer


def find(page: PageText, text: str):
    return next(word for word in page.words if word.text == text)


def test_text_layer_reads_words_and_lines(letter_pdf):
    pages = read_text_layer(letter_pdf)
    assert [(p.number, p.source) for p in pages] == [(1, "text_layer"), (2, "text_layer")]
    assert "12.03.2026 № 55/07-1234" in pages[0].text.splitlines()
    assert pages[1].text == "Приложение на 2 листах"


def test_positions_are_relative_and_match_layout(letter_pdf):
    page = read_text_layer(letter_pdf)[0]
    for word in page.words:
        assert 0 <= word.x0 < word.x1 <= 1 and 0 <= word.y0 < word.y1 <= 1

    date = find(page, "12.03.2026")
    assert date.x0 < 0.5 and date.y0 < 0.2  # chap yuqorida
    tashkent = find(page, "Ташкент")
    assert tashkent.x0 > 0.5 and tashkent.y0 < 0.2  # o'ng yuqorida — qabul qiluvchi bloki
    signer = find(page, "Сидоров")
    assert signer.y0 > 0.7  # pastda


def test_max_pages(letter_pdf):
    assert len(read_text_layer(letter_pdf, max_pages=1)) == 1
