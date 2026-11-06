# CAPE-Pins: halol yakuniy tahlil va baho

**Sana:** 2026-11-06. **Holat:** v1, v2 va v2.1 o'lchovlari yakunlangan, auditlar tasdiqlangan.

**Qoidalar:**
- Har bir raqam haqiqiy run'lardan olingan, hech bir namuna olib tashlanmagan.
- "Talqin" deb belgilangan joylar o'lchov emas, bizning izohimiz.
- Ishonchlilik darajasi har bo'limda ko'rsatilgan:
  - **confirmatory** — oldindan muzlatilgan, ko'rilmagan ma'lumot;
  - **exploratory** — ko'rilgan ma'lumot yoki kam klaster.

---

## 0. Qisqa javob

1. **Yutgan asosiy joyimiz:** Crackle formatining o'z pin optimizatoriga nisbatan. Fayl doim kichik yoki teng chiqadi
   (CREMI'da −0.11…−0.13%, katta Crackle hajmlarida −0.64…−0.73%). Kodlash geometrik o'rtachada 3.4–29× tez
   (alohida crop'larda 1.5–45×), xotira ~2× kam,
   fayl esa o'zgartirilmagan Crackle dekoderi bilan ochiladi.
2. **Eng muhim topilma:** upstream Crackle'dagi **jim ma'lumot buzilishi** xatosi (F2). CAPE undan xoli.
3. **Yutqazgan asosiy joyimiz:** arxivda (zstd bilan) oddiy `crackle_flat` + zstd ko'p namunada bizdan kichik.
   Encode tezligida esa flat va oddiy kompressorlar bizdan 3–16× tez.
4. **Yutuq tuzilmaviy cheklangan.** CAPE faylning faqat label bo'limini yaxshilaydi. Bu bo'lim CREMI faylining
   ~5–15% ini tashkil qiladi, shuning uchun umumiy yutuq 1% dan oshmaydi.
5. **Sinab ko'rilgan, lekin ishlamagan g'oyalar:**
   - zstd'ga moslashtirilgan refinement: atigi +0.01%, vaqt 2.7–3.9×;
   - CREMI'da depth-regime qidiruvi: 0 B.
6. **Q1 jurnal uchun bahomiz: 4/10.** Metodologiya kuchli, lekin ilmiy yangilik va hajm yutug'i kichik,
   mustaqil ma'lumotda tasdiq yo'q.

---

## 1. Manbalar va ishonchlilik

| Run | Ma'lumot | Rol | Ishonchlilik |
|---|---|---|---|
| `20261105T122347Z_all_d1a76eb7` (v1) | CREMI B/C, 24 crop, 12 klaster | v1 held-out | **confirmatory** (2 volume ichida) |
| `20261106T044558Z_all_83c337ae` (v2 test) | CREMI B/C ning hech qachon o'lchanmagan z 64–123 qatlamlari, 24 crop | v2 test | volume ichida umumlashuv (mustaqil emas) |
| `20261106T062540Z_development_0227806a` (Z=512) | Crackle repo, 4 crop (2 tasida Z=512) | width | exploratory |
| `20261106T091815Z_development_73f40dd8` (+ stock `..._9be56574`) | 25 nested crop, 134M vokselgacha | masshtab | exploratory, qiyaliklar tavsifiy |
| `analysis/v21_speedup` | 16 crop × 34 kombinatsiya | tezlashuv sabablari | development |

Auditlar (`analysis/v1_audit`, `v2_audit`, `v21_audit`) xom CSV'dan mustaqil qayta hisoblangan: hammasi
**verified**, takrorlarda bayt nodeterminizmi 0.

**Asosiy cheklov:** barcha real ma'lumot ikki manbadan olingan, CREMI (A/B/C) va Crackle repo namunalari.
CREMI'dan mustaqil SNEMI3D tayyorlangan, lekin hali o'lchanmagan.

---

## 2. Algoritm qanday tuzilgan va nega xatosiz

### 2.1. Vazifa

Crackle-v1 fayli bir necha bo'limdan iborat: header, z-indeks, chegara (crack code) va **label bo'limi**.
Biz faqat label bo'limiga tegamiz. Unda har bir label uchun qaysi CC (har bir z-qatlamdagi bog'langan
komponent) qaysi label'ga tegishli ekani ikki usulda yoziladi:
- **pin**: `(boshlang'ich indeks, chuqurlik)`; bitta ustun bo'ylab bir nechta qatlamdagi CC'larni birdaniga belgilaydi;
- **singleton**: CC id'ni alohida yozadi.

Maqsad: barcha CC'larni eng kam bayt bilan qoplash. Bu **og'irlikli set cover** masalasi. Har bir yozuvning
narxi formatning maydon kengliklaridan aniq hisoblanadi (formula (3), upstream bilan aniq mos).

### 2.2. Pipeline

```
kirish (labels) ──► [1] Skan: max label, flat/pins qoidasi (upstream bilan bir xil)
                    [2] Format qarori: same_as_stock | force_pins | min_exact
                    [3] Chegara (crack codes)      ◄─ upstream kodi, o'zgarishsiz
                    [4] CC belgilash               ◄─ upstream kodi, o'zgarishsiz
                    [5] Runs: har ustunda bir xil label'li maksimal z-qatorlar
                    [6] Nomzodlar (depth oynalari; FAST'da faqat to'liq kenglik)
                    [7] Xavfsiz qisqartirishlar:
                          singleton dominance → equal coverage (hash + element-wise) → subset dominance
                    [8] Mustaqil komponentlar (union-find)
                    [9] Pass 1: greedy (yuqori chegara UB) + integer dual (quyi chegara LB)
                   [10] Fon label'i: argmax UB (K marta qayta yechmasdan, isbotlangan formula)
                   [11] Pass 2: kichik komponentlarda aniq bitmask DP (n ≤ 20), qolganlarida local search
                   [12] Kenglikni siqish: w_N = width(max(P,Q))   ◄─ F2 xatosining tuzatilishi
                   [13] Serializatsiya (qat'iy overflow tekshiruvi) + bayt modeli = haqiqiy uzunlik
                ──► oddiy Crackle-v1 fayli (stock dekoder ochadi)
```

**Mahsulot variantlari:**
- **CAPE-FAST** (`cape_fast_*`): depth-regime qidiruvi o'chirilgan, sertifikatsiz.
- **CAPE-CERTIFIED** (`cape_certified_*`): FAST bilan bayt-bayt bir xil fayl, qo'shimcha ravishda optimallik sertifikati.
- **SAFE-ARCHIVE** (`safe_archive_*`): flat va CAPE stream'larining ikkalasini zstd bilan o'raydi va kichigini saqlaydi.
  Bu engineering bazasi, ilmiy hissa emas.
- **SAFE+refine** (`safe_refine_*`): **EKSPERIMENTAL**. Faylni haqiqiy zstd hajmi bo'yicha qayta yaxshilashga urinadi.

### 2.3. Nega xatosiz: kafolatlar zanjiri

| Kafolat | Qanday ta'minlangan | Tekshiruv |
|---|---|---|
| CC'lar upstream bilan bir xil | CC belgilash va chegara bo'limi upstream kodi bilan, o'zgarishsiz | `test_cc_labeling_equals_upstream` |
| Har bir pin o'z label'ining run'i ichida | nomzodlar faqat bir xil label'li maksimal run'lardan olinadi | matematik isbot (mathematics.md §9) |
| Har bir yozilgan CC qoplangan | har bir qabul qilingan tanlov qoplama sifatida qayta tekshiriladi | encoder ichida, har safar |
| Qisqartirishlar optimumni buzmaydi | witness zanjiri isboti; hash to'qnashuvi turli to'plamlarni hech qachon birlashtirmaydi (element-wise solishtirish) | `test_each_reduction_keeps_optimum`, majburiy to'qnashuv testi |
| Count maydoni to'lib ketmaydi (F2) | `w_N` aniq yozuvlar sonidan hisoblanadi; serializer overflow'ni rad etadi | adversarial namuna: stock 256 voksel buzadi, CAPE 270/270 to'g'ri |
| Bayt modeli = haqiqiy fayl | serializatsiyadan keyin uzunlik solishtiriladi | encoder ichida |
| Determinizm | tasodif yo'q, budjetlar vaqtga emas, o'tishlar soniga bog'liq; teng holatlar indeks bo'yicha hal qilinadi | takrorlarda nodeterminizm 0 |
| Xotira cheklovi jim kesishsiz | xotira oldindan bashorat qilinadi; oshsa `OOM_PREVENTED`, yashirin qisqartirish yo'q | `memory_cap_bytes` |
| Yakuniy tekshiruv | **har bir** benchmark qatori o'zgartirilmagan PyPI Crackle dekoderi bilan voksel bo'yicha solishtiriladi | v1: CAPE 2760/2760; v2: 6840 + 240 + 600 + stock qatorlari, xato 0 |
| v2 tezlashuvi baytni o'zgartirmaydi | 540 ta golden v1 bitstream; 5 o'zgarishning 32 kombinatsiyasi baytma-bayt bir xil | `test_golden_v1.py`, `test_impl_mask.py` |

**Testlar:** 1841 unit/matematik/interop testi va 12/12 acceptance testi o'tadi.

**Optimallik qaysi ma'noda:**
- Sertifikat faqat **cheklangan model** ichida amal qiladi: pins formati, nomzodlar oilasi, fon formulasi.
  Bu barcha mumkin bo'lgan Crackle fayllari ichida global optimum degani emas (FLAT format va boshqa
  CC raqamlash model tashqarisida).
- CP-SAT oracle 200/200 komponentda OPTIMAL natija bilan mos keldi.

---

## 3. ✅ Kimni, qayerda, qanday yutdik

### 3.1. Crackle stock pin optimizatori (`crackle_pins_opt`, PyPI 0.53.0 / vendor / tuzatilgan)

**Bu bizning asosiy raqibimiz.** Format bir xil, dekoder bir xil, faqat label bo'limini tanlash farq qiladi.

| Kategoriya | Ma'lumot | Natija | Ishonchlilik |
|---|---|---|---|
| Hajm (raw) | v1 held-out CREMI B/C | **−0.132%** (685 B), 23 kichik / 1 teng / 0 katta, CI [0.99840, 0.99898] | confirmatory |
| Hajm (raw) | v2 test CREMI B/C | **−0.107%** (573 B), 23 / 1 / 0, CI [0.99875, 0.99914] | volume ichida |
| Hajm (raw) | Z=512 width, 4 crop | **−0.733%**, 4 / 0 / 0 | exploratory |
| Hajm (raw) | masshtab, 19 crop (≤ 2^25 voksel) | **−0.640%**, 15 / 4 / 0 | exploratory |
| Hajm, Markov 5 | v1 held-out | −0.183% | confirmatory |
| Hajm + zstd9 | v1 / v2 test | −0.170% / −0.135% (22 / 1 / 1) | confirmatory / volume ichida |
| Encode tezligi | v1 held-out | **3.41×** tez, CI [3.15, 3.70] | confirmatory |
| Encode tezligi | v2 test (FAST) | **5.63×** tez (31.2 ms va 165.6 ms) | volume ichida |
| Encode tezligi | Z=512 width | **29×** (geo), CI [6.1, 89.7] | exploratory |
| Encode tezligi | masshtab, 19 crop | 5.1× (geo); 512²×128 da **36×** (0.62 s va 22.4 s) | exploratory |
| Xotira (peak) | v2 test | 81.6 MiB va 133.5 MiB (**−39%**) | volume ichida |
| Xotira (peak) | masshtab | ~2× kam (512²×128: 448 va 908 MiB) | exploratory |
| To'g'rilik | adversarial namuna | stock: **16 FAILED_LOSSLESS** (256 voksel jim buziladi); CAPE: 270/270 | deterministik reproducer |
| Decode | hammasi | teng (bir xil dekoder) | — |

**Qaysi qismimiz yutdi:**
- **Hajm:** stock → weighted_greedy → CAPE ketma-ket taqqoslashida farqning ~74% i (685 B dan 507 B)
  **haqiqiy bayt narxini hisobga oluvchi maqsad funksiyasidan** keladi (v1 ablation). Qolganini local search
  (79 B), aniq DP (42 B), fon formulasi (15 B) beradi. Katta hajmlarda yutuq kattaroq, chunki komponentlar
  yirik va stock'ning greedy tanlovi ko'proq bayt yo'qotadi.
- **Tezlik:**
  - v1 da xavfsiz qisqartirishlar (dedup 3.6×, dominance 1.3×) va greedy o'rniga strukturali yechim.
  - v2 da qo'shimcha 1.76–3.06× (2.4-bo'lim).
  - Stock Crackle connectomics'da vaqti ∝ V^1.87, bizniki ∝ V^1.25; shuning uchun katta hajmda farq keskin o'sadi.
- **To'g'rilik:** `w_N` maydonini aniq yozuvlar sonidan hisoblash (13-qadam).

**v1 da yutqazib, v2 da tuzatilgan joy:** ko'p label'li ws crop'da (256²×512) v1 stock'dan 1.6× **sekin** edi
(9.1 s va 5.3 s). v2 FAST endi 3.1× **tez** (1.66 s va 5.14 s).

### 3.2. Crackle'ning tezkor pin rejimi (`crackle_pins_fast`)

- v1 held-out'da **−1.83%**, 24/24 namunada kichik.

### 3.3. Ichki bazaviy selektorlar (bir xil format, panel A)

| Selektor | CAPE'dan qancha katta | Yomonroq namunalar | Vaqti |
|---|---|---|---|
| `stock_cover` (upstream tanlovi) | +685 B | 23/24 | 3.2× sekin |
| `weighted_greedy` | +178 B | 22/24 | 1.4× sekin |
| `greedy_local` | +87 B | 19/24 | 10.6× sekin |

### 3.4. Boshqa formatdagi zamonaviy siqish usullari (v1 held-out, hajm)

| Usul | CAPE'ga nisbatan |
|---|---|
| Neuroglancer compressed_segmentation | 20.4× katta |
| CSGV-R (Volcanite) | 11.3× katta |
| CSGV | 8.2× katta |
| Blosc2 | 7.8× katta |
| Compresso | 6.0× katta |
| zstd9 (xom massiv) | 3.4× katta |
| lzma6 | 2.1× katta |

⚠ **Halol izoh:** bu ustunlikning deyarli hammasi **Crackle formatining** xizmati. CAPE unga atigi 0.1–0.7%
qo'shadi. Buni CAPE'ning ilmiy yutug'i sifatida ko'rsatish noto'g'ri bo'ladi.

### 3.5. Flat format (zstd'siz)

- v2 test'da CAPE jami **−0.20%** kichik, lekin namunalar bo'yicha natija aralash: 12 kichik / 2 teng / **10 katta**.
- v1 held-out'da jami −0.32%; 3 namunada flat kichikroq.

### 3.6. v1 → v2 o'z-o'zimizga nisbatan (baytlar bir xil)

| Ma'lumot | Jami tezlashuv | Kod optimallashtirish | Algoritmik | Depth-regime'ni o'chirish |
|---|---|---|---|---|
| CREMI A (12 crop) | **1.76×** [1.67, 1.86] | 1.37× (55%) | 1.28× (44%) | 1.00× (0.5%) |
| Crackle (4 katta crop) | **3.06×** [2.04, 4.59] | 1.50× (36%) | 1.54× (39%) | 1.32× (25%) |

- **Kod optimallashtirish:** ustun bo'yicha xotira joylashuvi (L) va arzon hash (H).
- **Algoritmik:**
  - sort O(M log M) o'rniga hash-jadval O(M) (T);
  - DP'da faqat erishiladigan holatlar (S).
- **Yangi qisqartirish qoidasi qo'shilmagan.**
- Xotira legacy'dan ~7% kam.

### 3.7. SAFE-ARCHIVE va flat + zstd9 (engineering)

- v2 test'da −0.174% (555 B), 9 kichik / 15 teng / 0 katta. Flat'dan katta bo'lmaslik tuzilish bo'yicha kafolatlangan.
- ⚠ Bu "ikkitadan kichigini tanlash", ya'ni engineering. **Ilmiy hissa sifatida ko'rsatilmaydi.**

---

## 4. ❌ Kimga, qayerda, qanday yutqazdik va bunga qaysi qismimiz sababchi

### 4.1. Arxivda (zstd bilan) flat + zstd ko'p namunada bizdan kichik

| Juftlik | Ma'lumot | CAPE kichik / teng / katta | Jami |
|---|---|---|---|
| `cape_m0+zstd9` va `flat_m0+zstd9` | v1 held-out | 5 / 0 / **19** | CAPE **+0.148%** katta |
| `cape_m5+zstd9` va `flat_m5+zstd9` | v1 held-out | 3 / 2 / **19** | CAPE **+0.232%** katta |
| `cape_m0+zstd9` va `flat_m0+zstd9` | v2 test | 9 / 0 / **15** | CAPE −0.065% (jami kichik, lekin ko'p namunada katta) |
| `cape_fast_m5+zstd9` va `flat_m5+zstd9` | v2 test | — | CAPE +32 B (+0.011%) |

v1 held-out'da eng kichik umumiy fayl `crackle_flat_m5+zstd9` (288 123 B). Eng yaxshi CAPE `cape_m5+zstd3`:
288 677 B (+0.192%).

**Sababchi qism:** **maqsad funksiyasi** (9–11-qadamlar) zstd'dan **oldingi** baytlarni minimallashtiradi.
- **Talqin:** pin yozuvlari flat formatning muntazam ro'yxatlariga qaraganda zstd bilan yomonroq siqiladi.
- **Tuzatishga urinish (refine)** faylni to'g'ridan-to'g'ri zstd hajmi bo'yicha baholadi. Natija atigi
  −0.01% (4.4-bo'lim). Demak bu yo'qotishni pins formati ichida tuzatib bo'lmaydi.
- Ishlaydigan yechim faqat SAFE (kichigini tanlash), u esa ilmiy hissa emas.

### 4.2. Encode tezligi: oddiy usullar bizdan tez

| Usul | Encode | CAPE'ga nisbatan | Ma'lumot |
|---|---|---|---|
| zstd3 | 3.7 ms | ~16× tez | v1 held-out |
| crackle_flat | 11.0 ms (v1) / 10.3 ms (v2) | **v1: 5.4×, v2: 3.0×** tez | v1 / v2 test |
| neuroglancer | 14.3 ms | ~4× tez | v1 |
| compresso | 16.3 ms | ~3.6× tez | v1 |
| blosc2 | 26.0 ms | ~2.3× tez | v1 |
| CAPE v1 / **CAPE-FAST v2** | 59.1 ms / **31.2 ms** | — | v1 / v2 test |

Masshtab sinovida flat median 42.7 ms, FAST 127.9 ms, ya'ni flat ~3× tez.

**Sababchi qism:** 5–8-qadamlar (runs, nomzodlar va ayniqsa **qisqartirishlar**). Masshtab sinovida
qisqartirish bosqichi encode vaqtining ~40% ini egallaydi (512³ connectomics: 1388 ms dan 3432 ms gacha).
Vaqti nomzodlar soniga ∝ N^1.0–1.2 bog'liq.

Eslatma: zstd, neuroglancer, compresso va blosc2 v2 da qayta o'lchanmagan. Ular bilan v2 taqqoslashi
**to'g'ridan-to'g'ri emas**, chunki crop'lar boshqa.

### 4.3. Decode va xotira: oddiy usullardan yomonroq

- **Decode:** stock Crackle bilan teng (~7 ms CREMI). zstd3 (4.7 ms) va neuroglancer (5.4 ms) dan sekin.
  Bu Crackle formatining xususiyati (dekoder label bo'limini har bir z-qatlam uchun qayta o'qiydi, F7).
- **Xotira:**
  - v2 test'da 81.6 MiB, flat 74.0 MiB;
  - katta hajmlarda kirishdan **2.3–3.5×** ko'p: CREMI 1250²×125 da 3.4 GiB, ws 512³ da 3.4 GiB;
  - masshtab qiyaligi ∝ V^0.63–0.88.
- **Sababchi qism:** CC hajmi (4V bayt), runs va nomzodlar massivlari (xotira formulasi 4V + 16R + 40M + 32N + 8E).

### 4.4. Refinement (EKSPERIMENTAL): kutilgan foyda bermadi

| Ma'lumot | SAFE'dan tejash | kichik / teng / katta | Encode narxi |
|---|---|---|---|
| v2 test (24) | 42 B (**0.013%**) | 10 / 14 / 0 | **2.73×** sekin |
| Z=512 (4) | 438 B (0.007%) | 4 / 0 / 0 | 3.94× sekin |
| masshtab (25) | 2 758 B (0.010%) | 16 / 9 / 0 | 3.64× sekin |
| pilot, faqat anchor harakati | 0 B | 0 / 12 / 0 | 1.68× sekin |

- **Sababchi qism:** refine'ning `cape/refine.py` qismi. Vaqtining asosiy qismi zstd emas (median 64 ms),
  **Python serializatsiyasi** (median 453 ms).
- Statistik jihatdan foyda barqaror (CI 1 dan past), lekin amalda ahamiyatsiz.
- **Qaror:** EKSPERIMENTAL rejimga o'tkazildi.

### 4.5. FAST rejimi Z=512 da depth-regime baytlarini yo'qotadi

| Crop | FAST katta (B) | % | Regime'lar narxi |
|---|---|---|---|
| connectomics 512³ | +24 075 | 0.64% | 3.4 s → 5.8 s |
| connectomics 256²×512 | +5 199 | 0.68% | 0.64 s → 0.99 s |
| connectomics 128²×512 | +1 269 | 0.69% | 0.13 s → 0.19 s |
| connectomics 64²×512 | +93 | — | — |
| ws 512³ | +45 | — | 7.1 s → 11.9 s |
| Z ≤ 256 bo'lgan 20 crop | 0 | 0 | — |

- **Sababchi qism:** FAST'ning mahsulot qarori (6-qadamda faqat to'liq kenglik).
- ⚠ **Halol tuzatish:** v1 hujjatlarida "depth-regime foyda bermaydi (0–12 B)" deb yozilgan edi. Bu faqat
  o'sha 4 crop uchun to'g'ri. Masshtab sinovi buni rad etdi: ayrim Z=512 hajmlarda regime'lar 0.69% gacha foyda beradi.
- **Ochiq savol:** regime'ni qachon yoqish kerakligini oldindan bilish qoidasi yo'q.

### 4.6. Katta hajmlarda optimallik kafolati zaiflashadi

| Ko'rsatkich | CREMI | Katta Crackle crop'lari |
|---|---|---|
| Aniq DP bilan yechilgan CC'lar (median) | 90% | **26%** |
| Eng yirik komponent | 103 CC | 8 072 CC (width), 10 369 CC (512³) |
| UB/LB gap, butun fayl (median) | 0.024% | **0.59%** (max 0.84%) |
| Model ichida qolgan joy | ≤148 B (0.03%) | ≤61 166 B (**0.70%**) |
| Yechish vaqti | — | ∝ (eng yirik komponent)^1.4–2.9 |

- **Sababchi qism:** 11-qadam. Aniq DP faqat n ≤ 20 CC'li komponentlarda ishlaydi, kattalarida local search
  qo'llanadi va u optimallikni kafolatlamaydi.
- Evristika optimumga har doim yetmaydi: held-out'da 9 dan 7 tasi, pilotda 14 dan 11 tasi yetdi.

### 4.7. Hajm yutug'ining tuzilmaviy shifti

- Label bo'limi CREMI B/C raw faylining ~5% i, CREMI A ning ~15.6% i. Zstd'li arxivda u test crop'larida
  median **7.5%**, pilotda 17.3%.
- Formula: G = (L/C)·r. L/C = 0.05 bo'lsa, label'ni 10% qisqartirish faylni atigi 0.5% qisqartiradi.
- CREMI'da CAPE isbotlangan quyi chegaraga allaqachon yetgan (≤0.03% joy qolgan).
- **Xulosa:** pins formati ichida bundan ortiq siqish deyarli mumkin emas. Bu algoritmning emas, **muammo
  qo'yilishining** chegarasi (Crackle-v1 mosligi sharti).

---

## 5. Qismlar bo'yicha hisob

| Qism | Hajmga hissasi | Tezlikka hissasi | Baho |
|---|---|---|---|
| Bayt-narxli maqsad (weighted set cover) | **asosiy**: ~507 B / 685 B (v1) | — | ✅ ishning yadrosi |
| Local search | 79 B | ~+1% vaqt | ✅ kichik |
| Aniq DP | 42 B; katta hajmda optimallikni oshiradi | ~+3% vaqt | ✅ kichik, lekin sertifikat uchun kerak |
| Integer dual LB + sertifikat | 0 B (kafolat beradi) | CERTIFIED: CREMI'da ~0%, Z=512 da +22% | ✅ ishonch |
| Xavfsiz qisqartirishlar | optimumni o'zgartirmaydi | dedup 3.6×, dominance 1.3× | ✅ tezlik |
| v2: hash-jadval guruhlash (T) | 0 B | 1.24–1.30× | ✅ algoritmik |
| v2: erishiladigan DP holatlari (S) | 0 B | 1.04–1.19× | ✅ algoritmik |
| v2: xotira joylashuvi + runs (L) | 0 B | 1.25–1.44× | ✅ kod |
| v2: arzon hash (H) | 0 B | 1.04–1.10× | ✅ kod |
| `w_N` ni to'g'ri hisoblash (F2 tuzatish) | kichik | — | ✅ **to'g'rilik** |
| Fon formulasi | 15 B | K marta qayta yechishdan qutqaradi | ⚪ |
| Dual gate | 0 B | ~3% tez | ⚪ |
| Kengaytirilgan nomzodlar | 0 B | ~0 | ❌ bu ma'lumotda foydasiz |
| Depth-regime qidiruvi | CREMI'da 0 B; Z=512 da 0…0.69% | Z=512 da 1.3–1.7× sekin | ⚠ ma'lumotga bog'liq; FAST'da o'chiq |
| Refinement (zstd bo'yicha) | 0.007–0.013% | 2.7–3.9× sekin | ❌ eksperimental |
| SAFE-ARCHIVE | flat+zstd'dan −0.17% | +12% vaqt | ⚪ engineering, hissa emas |

---

## 6. Ma'lumot turlari bo'yicha qayerda yaxshi, qayerda yomon

| Ma'lumot | Stock'ga nisbatan hajm | Stock'ga nisbatan tezlik | Izoh |
|---|---|---|---|
| CREMI (kichik crop, Z=64–125) | −0.05…−0.13% | 3.4–5.6× | label bo'limi kichik, optimumga deyarli yetilgan |
| Crackle connectomics (katta, Z ≤ 256) | −0.2…−0.8% | 2.3–36× | eng yaxshi joyimiz |
| Crackle connectomics, Z=512 | −0.4…−0.96% | 5–45× | regime'lar bilan yana 0.69% gacha mumkin |
| Crackle ws (ko'p label) | −0.24…−0.64% | 2.5–3.7× | tezlik farqi eng kichik shu yerda |
| Juda kichik crop'lar (≤ 128³) | 0…−0.07% | 1.5–5× | ko'p hollarda stock bilan teng |

---

## 7. Halol baho

### 7.1. Kategoriyalar bo'yicha (10 ballik)

| Mezon | Ball | Asos |
|---|---|---|
| Metodologiya, takrorlanuvchanlik, audit | **9** | freeze → test, mustaqil audit, deterministik natijalar, salbiy natijalar ochiq |
| To'g'rilik va kafolat | **8** | 100% lossless, stock dekoder bilan mos, sertifikat; F2 topilgan |
| Tezlik (stock'ga nisbatan) | **7** | geo 3.4–29× (crop'larda 1.5–45×); flat'dan esa 3× sekin |
| Hajm yutug'i | **2** | 0.1–0.7%; arxivda flat + zstd bilan aralash natija |
| Ilmiy yangilik | **3** | weighted set cover, qisqartirishlar va DP standart usullar; yagona yangi g'oya (refine) ishlamadi |
| Umumlashuv dalili | **3** | ikki manba (CREMI, Crackle); SNEMI3D o'lchanmagan |
| Amaliy ta'sir | **4** | Crackle foydalanuvchilari uchun foydali (tezlik + F2), boshqalar uchun cheklangan |
| Adabiyot bilan taqqoslash | **4** | entropy-aware set cover adabiyoti ko'rilmagan |

**Q1 jurnal uchun umumiy baho: 4/10.** Realistik shift taxminan 6/10: SNEMI3D tasdig'i, ikkinchi mustaqil
oila, maqolani "tez, aniq, Crackle bilan mos optimizer + F2" deb qayta pozitsiyalash va upstream'ga qabul
qilinish bilan.

### 7.2. Da'vo qilish mumkin (dalili bor)

- Crackle-v1 bilan to'liq mos, stock dekoder ochadigan, stock optimizatordan **hech qachon katta bo'lmagan**
  (o'lchangan barcha real namunada) va geometrik o'rtachada 3.4–29× tez pin tanlash.
- Cheklangan model ichida tekshiriladigan optimallik sertifikati: CREMI'da gap ~0.02%.
- Upstream Crackle'dagi jim buzilish xatosi (F2), reproducer va tuzatilgan baseline bilan.
- v1 → v2 tezlashuvining bosqichlar bo'yicha sababiy ajratilishi (factorial + Shapley).

### 7.3. Da'vo qilib BO'LMAYDI

- "Eng kichik arxiv fayl": flat + zstd ko'p namunada kichik.
- "Zamonaviy usullardan 6–20× yaxshi" CAPE yutug'i sifatida: bu Crackle formatining xizmati.
- SAFE'ning "kichigini tanlash"i ilmiy yangilik sifatida.
- Refinement foydasi (ahamiyatsiz).
- Natijalarning CREMI va Crackle'dan tashqariga umumlashuvi (hali tasdiqlanmagan).
- "Global optimal Crackle fayli": sertifikat faqat cheklangan modelga tegishli.

---

## 8. Keyingi qadamlar (ta'siri bo'yicha)

1. **SNEMI3D tasdiqlovchi run** (tayyor; `configs/confirm_snemi3d.yaml`). Faqat foydalanuvchi buyrug'i bilan.
2. **Depth-regime'ni qachon yoqish** qoidasi (masalan, Z > 256 va komponent statistikasi bo'yicha). Hozir FAST
   Z=512 da 0.69% gacha yo'qotadi.
3. **Katta komponentlar uchun yaxshiroq qidiruv** (LNS; hozir to'xtatilgan). Model ichida 0.7% gacha joy bor.
4. **Adabiyot tahlili** (entropy-aware / compression-aware set cover) va buzilgan kirish testlari.
5. **Upstream'ga hissa** (F2 tuzatish, tez optimizer). Loyiha egasining qarori.

---

## 9. Fayllar

| Nima | Yo'l |
|---|---|
| v1 yutuq/yutqazishlar (batafsil) | `docs/YUTUQ_VA_YUTQAZISHLAR_UZ.md` |
| v2 yakuniy hisobot | `analysis/v2_final/V2_YAKUNIY_HISOBOT_UZ.md` |
| v2.1 hisobot (masshtab, vaqtlar, tezlashuv sabablari) | `analysis/v21_final/V21_HISOBOT_UZ.md` |
| Tezlashuv atributsiyasi | `analysis/v21_speedup/` |
| Auditlar | `analysis/v1_audit/`, `analysis/v2_audit/`, `analysis/v21_audit/` |
| Algoritm va matematika | `docs/algorithm.md`, `docs/mathematics.md` |
| Format auditi (F1–F10) | `docs/format_audit.md` |
| Qarorlar va Q1 tekshiruvi | `docs/MODERNIZATSIYA_QARORLARI_UZ.md` |
| SNEMI3D | `docs/MUSTAQIL_DATA_SNEMI3D_UZ.md` |
