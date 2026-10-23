"""Javob shakli: maydonlar ro'yxati va to'g'ri javob json'idan boshqarmani o'qish.

Buni ham model (o'rganishda), ham baholash ishlatadi.
"""

REKVIZIT_FIELDS = [
    "hujjat_junatuvchi_tashkilot",
    "hujjat_sana",
    "hujjat_raqami",
    "imzolagan_shaxs",
    "hujjatning_qisqacha_mazmuni",
]
ALL_FIELDS = [*REKVIZIT_FIELDS, "boshqarma"]


def expected_boshqarma(truth: dict) -> str | None:
    """Kutilgan boshqarma: `asosiy_ijrochilar_boshqarmalari` to'la bo'lsa o'sha,
    bo'sh bo'lsa `asosiy_ijrochilar` (u yerda viloyat adliya boshqarmasi turadi).

    Bu qoida 100 ta json tahlilidan chiqdi; rahbardan tasdiq kutilmoqda.
    """
    task = (truth.get("tasks") or [{}])[0]
    names = task.get("asosiy_ijrochilar_boshqarmalari") or task.get("asosiy_ijrochilar") or []
    return names[0] if names else None


def group_of(boshqarma: str | None) -> str:
    """Boshqarmaning guruhi: bo'linish va hisobotda ishlatiladi."""
    low = (boshqarma or "").lower()
    if "xalqaro" in low:
        return "xalqaro"
    if "notariat" in low:
        return "notariat"
    if "adliya" in low:
        return "viloyat"
    return "noma'lum"
