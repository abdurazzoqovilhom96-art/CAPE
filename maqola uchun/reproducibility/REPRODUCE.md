# Reproduce

Environment: Windows 11, Python 3.12, MinGW-w64 g++ 16.2 (see freeze.json for every hash).

```powershell
py -3.12 scripts\bootstrap.py                                  # venv + hashed lock + native build
.venv-fetch\Scripts\python scripts\fetch_external_q1.py --j0126 --hemibrain   # external data (authorized sources)
.venv\Scripts\python scripts\make_q1_manifests.py             # refuses to rewrite frozen manifests
.venv\Scripts\python.exe tools\q1_pipeline.py --mode full --fresh-run --output "maqola uchun"
.venv\Scripts\python.exe tools\q1_pipeline.py --mode render --run-id q1_20261107T072741Z --output "maqola uchun"
```
Seeds: 20261107 (bootstrap, randomized order). Source hash: f3fa7321f96a57edeb1a2f816ee4031c0ccd14865e930b7263087793ef21897a.
Frozen binaries: E0 f1029e19992af218a73437050abf750da811f318d36c4993834262785b01e98c, v2.1 39dca94b1eeb1c59c98b1dcb117e2f46c3b4ddf6b3539dd067c2a4f40a4ff2cb, Eθ 4bf56afc7259c275b98c9b41dde7c39f40a5555c4455dabf38bb3f286be536cf.
Datasets are not redistributed (licences); manifests give source URLs, coordinates and SHA-256.
