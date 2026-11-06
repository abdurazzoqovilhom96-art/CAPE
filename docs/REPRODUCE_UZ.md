# Qayta bajarish (reproduce)

Barcha buyruqlar `D:\CAPE_PINS` ichida, PowerShell'da.

## 0. Muhit
```powershell
py -3.12 scripts\bootstrap.py          # venv + lock + vendor + native + doctor
.venv\Scripts\python -m pytest tests -m "not acceptance"
.venv\Scripts\python -m pytest tests -m acceptance        # T1-T12 -> tests_acceptance.json
```

## 1. Smoke (sintetik + Crackle namunasi croplari)
```powershell
.\run_experiment.cmd --stage smoke
```

## 2. Real ma'lumot (CREMI, ruxsat berilgan)
```powershell
.\run_experiment.cmd --fetch-data cremi
```
Bu: rasmiy sahifadan havolalarni aniqlaydi, A/B/C ni yuklaydi (SHA-256 yoziladi), deterministik
macroblock croplarni tayyorlaydi va `data\manifests\pilot.jsonl` (A, development) hamda
`data\manifests\benchmark.jsonl` (B/C, held-out) ni yaratadi. Koordinatalar:
`data\manifests\crop_table_cremi.csv`.

## 3. Pilot (development)
```powershell
.\run_experiment.cmd --stage pilot --manifest ".\data\manifests\pilot.jsonl"
```

## 4. Held-out benchmark (freeze avtomatik)
```powershell
.\run_experiment.cmd --stage all --manifest ".\data\manifests\benchmark.jsonl" --config ".\configs\benchmark.yaml" --resume
```

## 5. Hisobot va tiklash
```powershell
.\run_experiment.cmd --stage report --latest     # yangi encode/decode/yuklash yo'q
.\run_experiment.cmd --stage recover --latest    # quvvat uzilishidan keyin
.venv\Scripts\python scripts\verify_results.py --latest
```

## Natijalar qayerda
`results\<run_id>\15_reports\RESULTS_INDEX.md` — kirish nuqtasi. Release:
`release\<run_id>\CAPE_PINS_SOURCE.zip`, `CAPE_PINS_RESULTS_<run_id>.zip`, `SHA256SUMS.txt`.
`SUCCESS.json` faqat so'ralgan bosqich va uning artifaktlari tekshiruvdan o'tganini bildiradi —
CAPE g'alaba qilganini emas.
