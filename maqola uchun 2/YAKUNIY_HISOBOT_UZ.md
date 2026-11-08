# B yo'nalishi: yakuniy hisobot (avtomatik yaratilgan)

**Texnik holat:** STOPPED_GATE_FAILED. **Ilmiy holat:** salbiy natija (gate o'tmadi)

## 0-bosqich: Q1 paketidagi tuzatishlar
- Holat: DONE; commit: 5927ee9 + 5876dbf; amendment run: results/20261107T183016Z_all_296f78da; neuroglancer_b8_u32 uint16 qatorlari: 704/704 uint16 rows SUCCESS, all lossless; paket validatori: 10/10 PASS (render 2 digest identical to render 1).

## Oldindan tekshiruvlar (G1)
- G1 = True (T03 jadvali). Teorema: mathematics/dominance_completeness_theorem.md.

## Prototip (development, 11 crop)
- CG to'liq yaqinlashdi: 11/11; integer yechim Eθ dan yomon emas: 1/11; L_CG >= L_ascent: 11/11.
- CG olib tashlashi mumkin bo'lgan native xotira ulushi (mediana): 1.2%; eng qulay holatdagi xotira nisbati (geo-mean): 0.9639.
- Candidate + reduksiya + komponent + solver vaqti ulushi (mediana): 21.9%.
- Proyeksiya (geo-mean): xotira 1.5349, vaqt 6.1074, sertifikat vaqti 6.0827; gap 42489 -> 1896 bayt.
- Tuzilish: Eθ yozadigan rejimda h = Z (11/11 crop), ya'ni CompleteWindows = har run'ga bitta oyna; CG 11/11 crop'da birinchi LP'da yaqinlashdi, pricing birorta ustun qo'shmadi.
- Sertifikat: gap mediana 0.689% -> 0.138% (U ga nisbatan); lekin vaqt 6.08x.
- Post-hoc (gate'ga kirmaydi, T08): iliq HiGHS vaqti bilan vaqt nisbati 2.502, sertifikat vaqti 2.757; xulosa o'zgarmaydi.

## Gate G2
- Yo'l M (xotira): False; yo'l T (vaqt): False; yo'l C (sertifikat): False. G2 = False.
- Native implementatsiya va final benchmark: NOT_RUN_GATE_FAILED.

## Halol baho (10 ballik, faqat shu B ishi uchun)
| Kategoriya | Ball | Asos |
|---|---|---|
| Matematik to'g'rilik | 9 | teorema isbotlangan, source bilan tekshirilgan, T1-T3 aniq solver bilan |
| Tajriba dizayni | 8 | gate va proyeksiya natijadan oldin qayd etilgan; faqat development, bitta mashina |
| Natija kuchi | 2 | gate o'tmadi |
| Yangilik | 2 | column generation va prefiks yig'indi ma'lum; teorema kichik element |
| Halollik | 9 | salbiy natija va cheklovlar ochiq; raqamlar xom fayllardan |

## Cheklovlar
- methods/LIMITATIONS_EN.md.

Hech narsa tashqariga yuborilmadi. Qayta yaratish: reproducibility/REPRODUCE.md.
