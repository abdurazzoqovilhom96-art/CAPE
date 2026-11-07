"""Frozen CAPE etalons: exact native modules copied to snapshots/<tag> before later changes, each with its
sha256 recorded in snapshots/<tag>/FROZEN_<TAG>.json and checked on load.

- v21: the v2.1 FAST binary (CAPE v3 protocol section 2; method cape_v21_fast_m0).
- v3:  the original v3 binary that ran the SNEMI3D confirm (source d07368c7; Q1 task v3 comparison C1, E0).

Each module is loaded from its own path under its original init name. Inside one process it shares pybind11's
exception translators with cape._cape_native (same C++ exception names), so an exception may surface as the other
module's Python class; the worker maps failures by class *name* (cape/worker.py::_status_for_exception), which is
unaffected. Streams are decoded with the original PyPI decoder exactly like every CAPE row.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from cape.adapters.base import AdapterUnavailable
from cape.adapters.cape_native import NATIVE_KEYS, CapeNativeAdapter

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = {
    "v21": {"dir": ROOT / "snapshots" / "v21", "record": "FROZEN_V21.json", "label": "v2.1", "max_mask": 31},
    "v3": {"dir": ROOT / "snapshots" / "v3", "record": "FROZEN_V3.json", "label": "v3", "max_mask": 1023},
}
FROZEN_DIR = SNAPSHOTS["v21"]["dir"]  # backwards compatible name (v2.1 etalon)
V3_ONLY_KEYS = {
    "regime_gate", "rc_fixing", "rc_max_cc", "rc_transitions_total", "rc_transitions_per_component", "rc_max_states",
    "repair", "repair_max_r", "repair_max_pool", "repair_attempts", "repair_transitions_total",
    "repair_transitions_per_attempt", "repair_max_states",
}
Q1_ONLY_KEYS = {"profile_memory"}  # unknown to both frozen modules
_MODULES: dict[str, object] = {}


def frozen_record(tag: str = "v21") -> dict:
    s = SNAPSHOTS[tag]
    return json.loads((s["dir"] / s["record"]).read_text(encoding="utf-8"))


def load_frozen_module(tag: str = "v21"):
    if tag in _MODULES:
        return _MODULES[tag]
    s = SNAPSHOTS[tag]
    try:
        rec = frozen_record(tag)
        path = s["dir"] / rec["file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, KeyError, ValueError) as exc:
        raise AdapterUnavailable(f"frozen {s['label']} module unavailable: {exc}") from exc
    if digest != rec["sha256"]:
        raise AdapterUnavailable(f"frozen {s['label']} module modified: sha256 {digest[:12]} != {rec['sha256'][:12]}")
    spec = importlib.util.spec_from_file_location("_cape_native", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _MODULES[tag] = mod
    return mod


class _CapeFrozenAdapter(CapeNativeAdapter):
    tag = "v21"

    def __init__(self, method_id, options=None, threads=1, base_options: dict | None = None):
        super().__init__(method_id, options, threads, base_options)
        s = SNAPSHOTS[self.tag]
        if self.tag == "v21":
            bad = set(self.native_options) & V3_ONLY_KEYS
            if bad:
                raise ValueError(f"{method_id}: v3-only option(s) {sorted(bad)} are not available in the frozen "
                                 f"v2.1 module")
        bad = set(self.native_options) & Q1_ONLY_KEYS
        if bad:
            raise ValueError(f"{method_id}: option(s) {sorted(bad)} are not available in the frozen {s['label']} module")
        mask = self.native_options.get("impl_mask", -1)
        if mask is not None and int(mask) > s["max_mask"]:
            raise ValueError(f"{method_id}: impl_mask {mask} uses bits the frozen {s['label']} module does not know "
                             f"(max {s['max_mask']})")
        assert set(self.native_options) <= NATIVE_KEYS

    def _modules(self):
        try:
            import crackle

            from cape import _crackle_vendor
        except ImportError as exc:
            raise AdapterUnavailable(f"native modules unavailable: {exc}") from exc
        return load_frozen_module(self.tag), _crackle_vendor, crackle

    def availability(self) -> dict:
        """File + checksum only: the module is loaded on the first encode, so availability tables never load it
        into a process that does not measure it (see the module docstring)."""
        s = SNAPSHOTS[self.tag]
        try:
            rec = frozen_record(self.tag)
            path = s["dir"] / rec["file"]
            ok = hashlib.sha256(path.read_bytes()).hexdigest() == rec["sha256"]
            import crackle  # noqa: F401

            from cape import _crackle_vendor  # noqa: F401
        except (OSError, KeyError, ValueError, ImportError) as exc:
            return {"status": "UNAVAILABLE_BUILD", "version": None, "reason": str(exc)}
        if not ok:
            return {"status": "UNAVAILABLE_BUILD", "version": None,
                    "reason": f"frozen {s['label']} module checksum mismatch"}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        try:
            sha = frozen_record(self.tag)["sha256"][:12]
        except (OSError, KeyError, ValueError):
            sha = "missing"
        return f"cape {SNAPSHOTS[self.tag]['label']} frozen binary (sha256 {sha})"


class CapeFrozenV21Adapter(_CapeFrozenAdapter):
    adapter_name = "cape_frozen_v21"
    tag = "v21"


class CapeFrozenV3Adapter(_CapeFrozenAdapter):
    adapter_name = "cape_frozen_v3"
    tag = "v3"
