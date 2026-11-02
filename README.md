# Xalqaro xatlar — PDF xatdan rekvizitlarni oflayn ajratish

MDH davlatlaridan keladigan **«Xalqaro huquqiy yordam»** xatlari (asosan rus tilida, ko'pi skaner PDF)
qo'lda ro'yxatga olinadi: xodim xatni o'qib, 6 ta maydonni to'ldiradi. Bu prototip shu ishni
**to'liq oflayn** bajaradi:

```
PDF kiradi → AI maydonlarni to'ldiradi → ishonchsiz joyga «⚠ Tekshiring» va takliflar → xodim tasdiqlaydi
```

Adliya vazirligi tizimidagi stajirovka doirasida qilingan (2026-yil oktabr).

## Nima ajratiladi

| Maydon | Qiyinligi |
|---|---|
| Jo'natuvchi tashkilot (o'zbekcha nomi) | ruscha blankdan tanish, notanish tashkilotga tarjima takliflari |
| Hujjat sanasi | ko'pincha qo'lda yoki shtamp bilan |
| Hujjat raqami | ko'pincha qo'lda, qoliplari har xil |
| Imzolagan shaxs (lotinda) | ruscha va ukraincha shakllar, yopishgan bosh harflar |
| Qisqacha mazmun | xat turiga qarab |
| Ijrochi boshqarma | viloyat, notariat yoki xalqaro-huquqiy hamkorlik |

Chiqish — xodim to'ldiradigan JSON'ning shu qismi (qiymatlar to'qilgan):

```json
{
  "rekvizit_document": {
    "hujjat_junatuvchi_tashkilot": "Rossiya Federatsiyasi Adliya vazirligining Novosibirsk viloyati bo'yicha bosh boshqarmasi",
    "hujjat_sana": "12.03.2026",
    "hujjat_raqami": "54/07-1234",
    "imzolagan_shaxs": "A.B.Sidorov",
    "hujjatning_qisqacha_mazmuni": "Xalqaro huquqiy yordam yuzasidan"
  },
  "tasks": [{"asosiy_ijrochilar_boshqarmalari": ["Farg'ona viloyati adliya boshqarmasi"]}]
}
```

## Asosiy tamoyil: ishonchli bo'lsa — yoz, ishonchsiz bo'lsa — taklif qil

Noto'g'ri qiymatni sezdirmasdan yozish — eng yomon natija. Shuning uchun har maydonda aniqlik bilan
birga **ishonchlilik** ham o'lchanadi.

| Holat | Tizim nima qiladi |
|---|---|
| Ishonchli | yozadi |
| O'rtacha | yozadi va «⚠ Tekshiring» qo'yadi |
| Ishonchsiz | yozmaydi, takliflar beradi (xodim bir bosishda tanlaydi) |
| Topilmadi | «⚠», PDF'da qidiriladigan joy ramka bilan ko'rsatiladi |

Har maydon PDF'ning qayeridan olingani sahifada rangli ramka bilan ko'rsatiladi.

## Natijalar

Ilgari hech qachon ko'rilmagan **125 ta yangi xatda**, bir marta o'lchangan:

| Maydon | Aniqlik | Bir bosishda* |
|---|---|---|
| Qisqacha mazmun | 97% | 97% |
| Boshqarma | 80% | 80% |
| Sana | 79% | 95% |
| Imzolagan shaxs | 79% | 79% |
| Raqam | 44% | 73% |
| Jo'natuvchi tashkilot | 26% | 54% |

\* yozilgan qiymat to'g'ri **yoki** to'g'risi takliflar ichida — xodimning real mehnati.

- **Baseline** («eng ko'p uchragan qiymatni hamma xatga yoz»): sana 11%, imzo 16%, raqam 3%.
- **Sana:** faqat PDF matnidan 19% → qo'lyozma bo'lagini VLM o'qib, boshqa OCR tasdiqlagach 77% (dev).
- **Jo'natuvchi:** yangi xatlardagi tashkilotlarning ko'pi o'rgatilgan xatlarda yo'q. Xodim tasdiqlab
  borsa (qayta aloqa), natija 28% → 56% (simulyatsiya, 25 xat).
- **Vaqt:** median ~40 s/xat, 8 GB RAM'li Mac'da, internetsiz.

### Qanday o'lchandi
- 100 ta xat loyihaning **birinchi kunida** bo'lindi: dev 70 / test 30 (stratifikatsiya, `seed=42`).
  Test xatlari qoida tanlashda ishlatilmaydi.
- Dev'da **leave-one-out**: har xat uchun model qolgan 69 tasidan quriladi.
- Har yangi qoida oldidan: nechta to'g'ri qo'shadi, nechta **xato** qo'shadi. Xato qo'shsa — rad.
- Kichik to'plamlar uchun 95% ishonch oralig'i (Wilson) hisoblanadi.
- O'lchov skriptlari prototip bilan **bir xil kodni** ishlatadi.

## Arxitektura

```
PDF ──► sahifa matni ──► maydon qoidalari ──► JSON
         │                 │                    + «tekshirish kerak» ro'yxati
         │                 │                    + takliflar
         │                 │                    + har maydonning PDF'dagi joyi
         │                 └─ model.json: dev xatlaridan o'rganilgan bilim
         │                    (tashkilot blanklari, boshqarma nomlari, raqam qoliplari)
         └─ matn qatlami (PyMuPDF) + Tesseract OCR (skaner sahifalar)

Qo'lyozma joylar (sana, raqam, imzo):
  1-sahifadan bo'laklar kesiladi
  → bir nechta OCR o'qiydi: Qwen3.5-2B VLM, RapidOCR, Tesseract, Apple Vision
  → ovoz berish: biri topadi, boshqa mustaqil OCR tasdiqlaydi
```

| Texnologiya | Vazifasi |
|---|---|
| PyMuPDF | PDF → matn qatlami va sahifa rasmi |
| Tesseract 5 | skaner sahifalar OCR'i |
| RapidOCR (PP-OCR, ONNX) | sana va raqam bo'laklari; rus tili uchun `eslav` modeli |
| Qwen3.5-2B-4bit VLM (mlx-vlm) | qo'lyozma sana va raqam; aniq savol, JSON javob |
| Apple Vision | qo'shimcha oflayn OCR (faqat macOS) |
| TF-IDF | jo'natuvchi blankini tanish |
| RapidFuzz | OCR xatolariga chidamli solishtirish |
| FastAPI + oddiy JS | prototip sahifasi: bitta xat yoki butun papka |

**Nega LLM asosiy yechim emas:** 8 GB RAM'ga faqat kichik model sig'adi (4B VLM sig'madi), LLM sana
yoki raqamni to'qishi mumkin. VLM faqat **o'qish** uchun ishlatiladi va uning javobi boshqa OCR
tasdiqlamasa avtomatik yozilmaydi.

## Maxfiylik

- Hammasi **oflayn**: bulut xizmatlari ishlatilmaydi, modellar internetsiz yuklanadi.
- VLM serveri faqat `127.0.0.1` da ochiladi; kod boshqa manzilni qabul qilmaydi.
- Real xatlar va natijalar (`data/real*`, `outputs/`) `.gitignore` da. Repo'da faqat kod.
- O'lchov skriptlari ekranga faqat sonlarni chiqaradi (ism va matn emas).

## Ishga tushirish

Talablar: macOS (Apple Silicon), Python 3.12–3.13, [Poetry](https://python-poetry.org/),
`brew install tesseract`.

```bash
# 1. Asosiy muhit
poetry install

# 2. VLM muhiti (alohida: mlx-vlm va rapidocr turli opencv paketini talab qiladi)
python3.13 -m venv .venv-vlm && .venv-vlm/bin/pip install mlx-vlm==0.7.10
.venv-vlm/bin/hf download mlx-community/Qwen3.5-2B-4bit --local-dir models/vlm/Qwen3.5-2B-4bit
```

3. Tesseract til paketlarini `models/tessdata/` ga qo'ying (kamida `rus.traineddata`).
4. RapidOCR rus modeli: `models/rapidocr/eslav_PP-OCRv5_rec_mobile.onnx`
   (havola va SHA256 — `src/reading/engines/rapid.py` da).

```bash
make start   # VLM + sahifa birga: http://127.0.0.1:8000
```

| Buyruq | Nima qiladi |
|---|---|
| `make start` | VLM va veb sahifani birga ishga tushiradi |
| `make vlm` / `make web` | ikkalasini alohida terminallarda |
| `make stop` | fonda qolgan serverlarni to'xtatadi |
| `make test` | testlar |
| `make lint` | ruff tekshiruvi va formatlash |
| `make model` | dev xatlaridan model va LOO javoblari (`data/real/` kerak, repo'da yo'q) |
| `make eval` | dev javoblarini baholash |

VLM ishlamasa ham sahifa ochiladi — faqat qo'lyozma sana va raqam o'qilmaydi.

## Testlar

```bash
make test
```

392 ta test, faqat to'qilgan ma'lumot bilan — real xatsiz ishlaydi.

## Kod tuzilishi

| Papka | Nima |
|---|---|
| `src/reading/` | PDF → matn: matn qatlami, Tesseract, rasm bo'laklari, OCR dvigatellari (`engines/`) |
| `src/fields/` | har maydon qoidasi: jo'natuvchi, sana, raqam, imzo, mazmun, boshqarma, ovoz berish |
| `src/engine/` | zanjir: `predict`, `date_ocr`, `number_ocr`, `signer_ocr`, `model`, `feedback`, `pipeline` |
| `src/evaluation/` | bo'linish, kesh, baholash |
| `src/web/` | FastAPI va sahifa (`/extract`, `/pages`, `/confirm`) |
| `scripts/` | o'lchov va tahlil skriptlari |
| `tests/` | testlar |
| `docs/REJA.md` | ish rejasi va bosqichlar |

## Cheklovlar

- **Qo'lyozma raqam:** xatlarning taxminan yarmida hech bir lokal OCR to'g'ri raqamni o'qiy olmaydi.
- **Notanish tashkilot** avtomatik yozilmaydi — taklif qilinadi, xodim tasdig'idan keyin o'rganiladi.
- **Test to'plami kichik** (30 xat) — ishonch oraliqlari keng.
- Faqat shu turdagi xatlarda (MDH, «Xalqaro huquqiy yordam») o'lchangan.
- Apple Vision faqat macOS'da; boshqa tizimda qoidalar Vision'siz ishlaydi.
