# CREMI'dan mustaqil tasdiqlovchi manba: SNEMI3D

**Holat (2026-11-06):** ma'lumot yuklandi, tekshirildi va croplar muzlatildi. **Bu ma'lumotda hali hech
qanday siqish o'lchovi o'tkazilmagan.** Tasdiqlovchi run faqat alohida so'rovdan keyin ishga tushiriladi
(`configs/confirm_snemi3d.yaml`).

## Manba

| Maydon | Qiymat |
|---|---|
| Nomi | SNEMI3D: 3D Segmentation of neurites in EM images (ISBI 2013) |
| Yozuv | Zenodo 7142003, DOI [10.5281/zenodo.7142003](https://doi.org/10.5281/zenodo.7142003) |
| Mualliflar | Arganda-Carreras I., Seung H. S., Vishwanathan A., Berger D. R. |
| Tasvir manbasi | Lichtman Lab (Harvard), Kasthuri va boshq. 2015 sichqon somatosensor po'stlog'i |
| Litsenziya | **CC-BY-4.0** (Zenodo metadata) |
| Fayl | `snemi.zip`, 194 608 530 B; md5 `3d25a7025f66698f33c7850ace885939` (Zenodo bilan mos); SHA-256 `59b72d89e14ddd4b…` (`data/downloads/snemi3d/download_log.json`) |
| Ishlatilgan qism | faqat `seg/train-labels.tif`: 100×1024×1024 (Z, Y, X), `uint16`, 401 ta label (0 bilan birga), ~15% voksel 0 ga teng |
| Ruxsat | foydalanuvchi, 2026-11-06 (plan v2.1). Ma'lumot qayta tarqatilmaydi |

Agar Zenodo yozuvidagi o'lcham, md5 yoki litsenziya ruxsat berilgan paytdagidan farq qilsa,
`scripts/fetch_snemi3d.py` to'xtaydi.

## Nega CREMI'dan mustaqil

| | CREMI (v1/v2 da ishlatilgan) | SNEMI3D |
|---|---|---|
| Tur | drozofila (kattalar miyasi) | sichqon (somatosensor po'stloq) |
| Laboratoriya va tasvirlash | Bock lab va FAFB ssTEM, 4×4×40 nm | Lichtman lab, ATUM-SEM |
| Annotatsiya | CREMI jamoasi | D. R. Berger (qo'lda) |
| Label turi | `uint64` | `uint16` |

v1/v2 dagi hech bir dizayn qarori, sozlama yoki freeze qoidasi bu ma'lumotga qarab tanlanmagan.

## Muzlatilgan crop qoidasi (siqishdan oldin yozilgan)

- 1024×1024 XY tekisligidagi 4×4 grid'ning **barcha 16 katagi**, z∈[0,64): 16 ta 256×256×64 crop.
- Har birining markazidan nested 128×128×64 crop: yana 16 ta. Jami **32 namuna, 16 macroblock klasteri**.
- Kontentga qarab tanlov yo'q. z 64–99 rezervda qoladi.
- Fayllar:
  - `data/manifests/confirm_snemi3d.jsonl` (`prepared_at` 2026-11-06T07:11:37Z);
  - `data/manifests/crop_table_snemi3d.csv`;
  - `data/real/snemi3d_crops/*.npy`.
- Label statistikasi (siqishsiz):
  - 256² croplar: median 56.5 label (34–73);
  - 128² croplar: median 29.5 label (17–39);
  - 0 ulushi median 11.8%.
- Qayta yaratish: `python scripts/fetch_snemi3d.py`, keyin `python scripts/freeze_data.py --snemi3d-confirm`.
  Manifest bor bo'lsa, ikkinchi buyruq uni qayta yozmaydi.

## Cheklovlar (halol)

- **Bitta volume.** Mustaqil ma'lumot oilasi bor, lekin u bitta volume'dan iborat, ko'p volume'li
  populyatsiya emas. CI 16 klaster bo'yicha hisoblanadi.
- **Faqat ikkinchi oila.** Q1 uchun hali ham kuchsiz. Uchinchi oila (masalan, H01, MICrONS yoki FlyEM
  hemibrain) qo'shimcha ruxsat talab qiladi: H01 va MICrONS uchun ruxsat berilmagan.
- **Crackle namunalarining kelib chiqishi noma'lum.** Agar ular ham Kasthuri volume'idan olingan
  bo'lsa, bu ikki manba qisman bog'liq bo'ladi. Buni tekshirib bo'lmadi, shuning uchun alohida
  yozilgan.
- **Spacing arxivda yozilmagan.** Manifestda `null`, sababi bilan.
