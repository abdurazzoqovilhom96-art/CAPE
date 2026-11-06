"""Task planning and resume keys (spec sections 20, 30): deterministic plan, method order
shuffled per repeat with a fixed seed, resume key = input+source+config+method+panel+repeat,
so results under another config/source are never reused."""

from __future__ import annotations

from types import SimpleNamespace

from cape.config import load_methods, load_run_config
from cape.provenance import ROOT
from cape.runner import plan_tasks

METHODS = load_methods(ROOT / "configs" / "methods.yaml")


def _ctx(cfg_hash: str, src: str = "src"):
    cfg = load_run_config("configs/smoke.yaml", METHODS)
    rows = [{"sample_id": f"s{i}", "voxel_sha256": f"{i:064x}", "split": "development", "is_synthetic": i == 0}
            for i in range(3)]
    return SimpleNamespace(cfg=cfg, methods=METHODS, rows=rows, hashes={"source": src, "config": cfg_hash})


def test_plan_is_deterministic_and_complete():
    a, b = plan_tasks(_ctx("c1")), plan_tasks(_ctx("c1"))
    assert [t["task_id"] for t in a] == [t["task_id"] for t in b]
    assert len({t["task_id"] for t in a}) == len(a)
    cfg = _ctx("c1").cfg
    per_repeat = [[(t["method_id"], t["wrapper"]) for t in a if t["sample_id"] == "s1" and t["repeat"] == r
                   and t["kind"] == "timed"] for r in range(cfg["benchmark"]["repeats"])]
    assert sorted(per_repeat[0]) == sorted(per_repeat[1])  # same combos every repeat
    assert per_repeat[0] != per_repeat[1]  # but a different, seeded order
    mem = [t for t in a if t["kind"] == "memory"]
    assert mem and all(t["sample_id"] != "s0" for t in mem)  # memory profiles only for real samples


def test_resume_keys_change_with_config_or_source():
    base = {t["task_id"] for t in plan_tasks(_ctx("c1"))}
    assert base.isdisjoint({t["task_id"] for t in plan_tasks(_ctx("c2"))})
    assert base.isdisjoint({t["task_id"] for t in plan_tasks(_ctx("c1", src="other"))})
