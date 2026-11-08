# CAPE-Pins

**Componentwise Adaptive Pin Encoding** — Crackle formatiga to'liq mos, 3D integer label
hajmlari uchun yaxshilangan pin encoder va natijani avtomatik chiqaradigan tajriba tizimi.
"CAPE-Pins" ishchi nom; global noyobligi tekshirilmagan.

CAPE yozgan har bir oqim oddiy Crackle v1 oqimi: uni **asl** decoder (PyPI `crackle-codec`
0.53.0) o'qiydi. CAPE faqat label bo'limida qaysi pin va CC yozuvlari yozilishini tanlaydi;
chegara (crack code) payload'i stock Crackle bilan bayt-bayt bir xil.

## Holat

Hozirgi holat, nima real bajarilgani va nima bloklangani: [`docs/HANDOFF_UZ.md`](docs/HANDOFF_UZ.md).
Bu README yoki spetsifikatsiyaning mavjudligi natija olinganini anglatmaydi; raqamlar faqat
`results/<run_id>/` ichidagi tekshirilgan yozuvlardan olinadi.

## Tez boshlash (Windows)

Talablar: CPython 3.12 (`py -3.12`), MinGW-w64 g++ (C++20), CMake >= 3.24, Ninja, git.
Batafsil: [`docs/WINDOWS_UZ.md`](docs/WINDOWS_UZ.md).

```powershell
.\run_experiment.cmd --stage smoke                       # sintetik + Crackle namunasi, to'liq zanjir
.\run_experiment.cmd --fetch-data cremi                  # CREMI A/B/C (ruxsat berilgan) + croplar
.\run_experiment.cmd --stage pilot --data ".\data\real"  # real pilot (development split)
.\run_experiment.cmd --stage all --manifest ".\data\manifests\benchmark.jsonl" --config ".\configs\benchmark.yaml" --resume
.\run_experiment.cmd --stage report --latest             # tajribasiz qayta hisobot
.\run_experiment.cmd --stage recover --latest            # uzilishdan keyin tiklash
```

Natijani ko'rish uchun: `results\<run_id>\15_reports\RESULTS_INDEX.md` (run oxirida absolyut yo'l
konsolga chiqariladi). `results\LATEST_RUN.txt` faqat eng oxirgi run manzili.

## Tuzilma

| Joy | Mazmun |
|---|---|
| `cpp/` | CAPE C++ yadrosi (runs, nomzodlar, qisqartirish, komponentlar, greedy, DP, local search, dual bound, serializer, upstream bridge) |
| `cape/` | Python pipeline: konfiguratsiya, I/O, adapterlar, runner/worker, SQLite store, statistika, figuralar, hisobotlar |
| `configs/` | run konfiguratsiyalari, metod/dataset/claim/artifact registrlari |
| `schemas/` | JSON schema'lar (dataset, measurement, certificate, status, artifact) |
| `scripts/` | bootstrap, build, doctor, ma'lumot, freeze, verify, package, recover |
| `tests/` | matematik, interop, adapter va T1–T12 acceptance testlari |
| `docs/` | matematika, format audit, algoritm, protokol, manbalar, cheklovlar |

## Asosiy qoidalar

- Natija uydirilmaydi: mavjud bo'lmagan usul `UNAVAILABLE`, ma'lumot yo'q bo'lsa `BLOCKED_DATA`.
- Yomon natija ham hisobotga kiradi; manfiy yutuq kesilmaydi.
- Sertifikatlar faqat `certificate_scope` da yozilgan cheklangan model uchun amal qiladi.
- Q1 yoki yangilik kafolati yo'q; da'volar faqat `claim_gate.json` ruxsat bergan doirada.

Litsenziya: CAPE kodi [BSD 3-Clause](LICENSE) (muallif: Ilkhom Abdurazzokov). Kompilyatsiya qilinadigan
uchinchi tomon header'lari o'z litsenziyalarida: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Boshqalar qanday foydalanadi

Python API (`cape.api.compress`), buyruq qatori (`python -m cape.api`), o'rnatish (Windows va Linux), natijalar
jadvali va qayta ishlab chiqarish: inglizcha [`README.md`](README.md).
