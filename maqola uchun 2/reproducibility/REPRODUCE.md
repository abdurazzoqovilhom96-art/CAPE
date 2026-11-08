# Reproduce (B protocol)

```powershell
py -3.12 scripts\bootstrap.py                                       # venv + native build (as for CAPE)
.venv\Scripts\python -m pytest tests\test_cg_prechecks.py -q          # G1 prechecks T1-T4
.venv\Scripts\python tools\run_research.py --mode full --fresh-run    # full B protocol run
.venv\Scripts\python tools\run_research.py --mode full --resume-run q1b_20261107T185232Z
.venv\Scripts\python tools\run_research.py --mode render --run-id q1b_20261107T185232Z   # rebuild this package only
```
Run id: `q1b_20261107T185232Z`; source hash `62a72a6ae625`; git `47d3a71`; environment
lock hash `fff2b4d2614d275a`; seed 20261107. Raw rows: `raw_results/`. Timing: one machine, one thread,
pinned P-core, nothing else running.
