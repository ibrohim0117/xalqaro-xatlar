"""number_consensus testlari — to'qilgan raqamlar bilan."""

from scripts.ocr.number_consensus import consensus


def test_consensus_builds_number_no_reader_saw():
    votes = [
        ("vlm-extract", {"12/8-46"}),  # 3-belgida adashgan
        ("apple-vision", {"12/3-40"}),  # oxirgi belgida adashgan
        ("rapidocr", {"12/3-46", "99"}),  # to'g'ri (va boshqa shakldagi nomzod)
        ("matn", set()),
    ]
    assert consensus(votes) == "12/3-46"


def test_consensus_needs_two_readers_and_prefers_finder_on_ties():
    assert consensus([("vlm-extract", {"12/3-46"}), ("matn", set())]) is None  # bitta OCR
    votes = [("vlm-extract", {"12/3-46"}), ("rapidocr", {"12/3-48"})]
    assert consensus(votes) == "12/3-46"  # teng ovoz — VLM aniq savol belgisi
    assert consensus(votes, skip=("vlm-extract",)) is None  # VLM'siz bitta OCR qoldi


def test_consensus_takes_shape_most_readers_saw():
    votes = [
        ("vlm-extract", {"12/3-46"}),
        ("vlm", {"123-456"}),
        ("rapidocr", {"123-450"}),
        ("apple-vision", {"123-456"}),
    ]
    assert consensus(votes) == "123-456"  # "999-999" ni 3 OCR o'qigan
