# Ish rejasi: xalqaro huquqiy yordam xatlari

**Maqsad:** MDH davlatlaridan kelgan skaner PDF xatdan rekvizitlarni ajratish va task uchun
boshqarmani aniqlash. Hammasi oflayn, real xatlar faqat ichki kompyuterda ishlanadi.

**Natija:** ishlaydigan prototip va aniqlik hisoboti.

**Kerakli maydonlar:** jo'natuvchi tashkilot (o'zbekcha, lotinda), hujjat sanasi, hujjat raqami,
imzolagan shaxs (lotinda), qisqacha mazmun, boshqarma.

---

## A. Qilingan ishlar

| # | Ish | Nega kerak edi |
|---|---|---|
| A1 | Vazifani o'rganish (qo'llanma, rahbar javoblari, skrinshotlar) | Nimani qurishni aniq bilish uchun |
| A2 | Maxfiylik qoidasi va loyiha tuzilishi | Real xatlar va natijalar gitga yoki tashqi xizmatga chiqmasligi uchun |
| A3 | Muhit: Tesseract (rus, qozoq, o'zbek), 13 ta kutubxona, zanjir tekshiruvi | Kod yozishga tayyor bo'lish uchun |
| A4 | Ma'lumotni tanish (faqat umumiy raqamlar) | Qaysi qism muhim va qiyin ekanini bilish uchun |

**A4 dan asosiy xulosalar (100 ta xat):**
- 88 tasida matn qatlami bor, 12 tasi to'liq skaner, ya'ni OCR faqat bir qismiga kerak.
- Boshqarma: **81% viloyat**, 16% notariat, 3% xalqaro-huquqiy hamkorlik.
- Viloyat adliya boshqarmasi `asosiy_ijrochilar` maydonida, boshqa ikkisi `asosiy_ijrochilar_boshqarmalari` da.
- Qabul qiluvchining manzili ("Ташкент, ул. Сайилгох, 5") **har bir xatda** bor, viloyatni aniqlashda chiqarib tashlanadi.
- Sana va raqam ko'pincha **qo'lda yoki shtamp bilan** yozilgan, sana formatlari har xil.
- "ПОВТОРНО" 8 ta xatda bor, ulardan 7 tasi baribir viloyatga yuborilgan.
- Qisqacha mazmun 85% holatda bir xil.

| # | Ish | Natija |
|---|---|---|
| B1 | Xatlarni bo'lish: 70 ta sozlash (dev), 30 ta imtihon (test), har guruhdan o'z ulushida | dev: viloyat 57, notariat 11, xalqaro 2; test: 24, 5, 1 |
| B2 | Baholash skripti va eng oddiy boshlang'ich natija ("har doim eng ko'p uchragan javob") | Pastki chegara (dev): mazmun 84.3%, boshqarma 18.6%, tashkilot 15.7%, imzo 15.7%, sana 11.4%, raqam 2.9% |
| B3 | PDF → matn: matn qatlami yoki OCR (Tesseract), har so'zning sahifadagi joyi bilan; kesh | 589 dev sahifa: 477 matn qatlamidan, 112 OCR'dan. OCR ~2.2 s/sahifa |

**B3 dan asosiy xulosalar (70 ta dev xat, dastlabki 2 sahifa):**
- **Sana ~2/3, raqam ~3/4 xatda matnga umuman tushmagan:** ular shtamp yoki qo'lda ko'k siyohda yozilgan,
  na skaner dasturi, na Tesseract o'qiy oladi. Matndan qidirish sana uchun ko'pi bilan 33%, raqam uchun 27%.
- **"№" belgisi 83% xatda topiladi** va doim sahifaning yuqori yarmida (odatda tepadan ~1/3 da). U sana-raqam
  qatorining joyini ko'rsatadi. Tesseract uni skaner dasturining matn qatlamidan yaxshiroq topadi (80% / 65%).
- Bosma matn (blank, qabul qiluvchi, xat matni) yaxshi o'qiladi. OCR'da chap va o'ng bloklar bitta qatorga
  qo'shilib ketadi, shuning uchun qatorlarga emas, **so'zlarning joyiga** tayaniladi.

---

## B. Qolgan ishlar (bajarilish tartibida)

### B4. Boshqarma (eng muhim, natijaning 81% i)
1. **Manzil → viloyat.** O'zbekiston viloyat va tumanlari ro'yxati tuziladi: ruscha shakllari, sovet
   davri nomlari ("Узбекская ССР", "Чирчикский горисполком") bilan. Qabul qiluvchining manzili chiqarib
   tashlanadi. Toshkent **shahri** va **viloyati** alohida ajratiladi, ular viloyat holatlarining 42% i.
2. **Manzil topilmasa:** notariat yoki xalqaro-huquqiy hamkorlik, xat mazmuniga qarab.
3. **"ПОВТОРНО" va indeks qoidasi.**

**Nega birinchi:** bu tizimning asosiy foydasi (xatni to'g'ri joyga yuborish) va bahoning eng katta qismi.

### B5. Rekvizitlar
| Maydon | Yondashuv | Qiyinligi |
|---|---|---|
| Hujjat sanasi va raqami | Matnda bo'lsa (~1/3) — "sana № raqam" qatoridan. Bo'lmasa — "№" langari bo'yicha qatorni rasmdan kesib, alohida o'qish (kerak bo'lsa qo'l yozuvi uchun lokal model). Sana formatlari bir ko'rinishga keltiriladi. "На № ... от ..." kabi tuzoqlar chetlab o'tiladi | Eng qiyin: shtamp va qo'lyozma |
| Imzolagan shaxs | Xat oxiridagi lavozim va ism. Kirilldan lotinga o'giriladi (Ш→Sh, Х→X) | O'rta |
| Jo'natuvchi tashkilot | Katalog bo'lsa, undan eng mosi topiladi. Bo'lmasa, lug'at va qoliplar asosida tarjima qilinadi | O'rta yoki qiyin |
| Qisqacha mazmun | Standart matn. Qolgan 15 ta holat o'rganiladi | Oson yoki noaniq |

**Qo'lyozma bo'yicha qoida:** noaniq o'qilgan qiymat o'rniga "tekshirish kerak" belgisi qo'yiladi.
Noto'g'ri sana bo'sh maydondan xavfliroq.

### B6. Aniqlik hisoboti
**Nega:** rahbar so'ragan asosiy natija. Har bir maydon bo'yicha foiz va xato turlari (masalan, "OCR
manzilni o'qiy olmadi", "Toshkent shahri va viloyati adashtirildi"). O'lchov 30 ta imtihon xatida
**bir marta** o'tkaziladi.

### B7. Prototip
- **API** (FastAPI): `POST /extract`. PDF qabul qiladi, JSON qaytaradi. Ichki tizimga ulash uchun.
- **Oddiy veb-sahifa:** chapda PDF, o'ngda AI to'ldirgan maydonlar. Namoyish uchun.

Telegram bot qilinmaydi, chunki hujjatlar tashqi serverga chiqib ketadi.

### B8. Hujjatlash
README (qanday ishga tushiriladi) va hisobot: tanlangan usullar, aniqlik, cheklovlar, keyingi qadamlar.

---

## C. Rahbardan javob kutilayotgan savollar

1. Boshqarma uchun `asosiy_ijrochilar` (viloyat) va `asosiy_ijrochilar_boshqarmalari` (ichki) birlashtiriladimi?
2. Qisqacha mazmuni boshqacha bo'lgan 15 ta holat. *Ibrohim xatlarni o'zi ko'rib chiqadi.*
3. "ПОВТОРНО" xatlarda indeks qoidasi aynan qachon qo'llanadi? To'liq indeks jadvali bormi?
4. Tizimdagi jo'natuvchi tashkilotlar katalogini olsa bo'ladimi?
5. Kod qayerda saqlanadi? Prototip qanday ko'rinishda bo'lishi kerak va muddati qachon?

## D. Xavflar

- **Qo'lyozma** sana va raqamlar: Tesseract ularni yaxshi o'qimaydi. Kerak bo'lsa, kuchliroq lokal OCR sinab ko'riladi.
- **Kam ma'lumot:** imtihon to'plamida bor-yo'g'i 30 ta xat, shuning uchun foizlar taxminiy bo'ladi.
- **Bir nechta viloyatli xat** namunalarda uchramadi. Kod uni qo'llab-quvvatlaydi, lekin real xatda sinalmagan.
- **Notanish tashkilotlar:** 33 tadan ko'p bo'lishi mumkin.
