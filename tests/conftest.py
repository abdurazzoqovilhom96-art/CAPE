"""Shared pytest fixtures. Native modules are imported eagerly on purpose: a missing build
is a collection error, never a silent skip (spec: no hidden fallback / fake success)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEED = 20261105


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(SEED)


_ACCEPTANCE: dict = {}


def pytest_runtest_logreport(report):
    """Record the real status of the T1-T12 acceptance tests (spec 38: tests_acceptance.json)."""
    if "test_acceptance.py" in report.nodeid and (report.when == "call" or report.outcome != "passed"):
        name = report.nodeid.split("::")[-1]
        _ACCEPTANCE[name] = {"outcome": report.outcome, "duration_s": round(report.duration, 2),
                             "detail": str(report.longrepr)[-1500:] if report.failed else None}


def pytest_sessionfinish(session, exitstatus):
    if _ACCEPTANCE:
        import datetime
        import json

        path = ROOT / "tests_acceptance.json"
        data = {"generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "tests": dict(sorted(_ACCEPTANCE.items())),
                "summary": {k: sum(v["outcome"] == k for v in _ACCEPTANCE.values()) for k in ("passed", "failed", "skipped")}}
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def as_xyz(zyx: np.ndarray) -> np.ndarray:
    """Canonical (Z,Y,X) C-order -> Crackle (X,Y,Z) F-order view (no copy)."""
    xyz = zyx.T
    assert xyz.flags.f_contiguous
    return xyz
