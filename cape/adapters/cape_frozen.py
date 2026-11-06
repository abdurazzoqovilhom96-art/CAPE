"""Frozen v2.1 CAPE etalon (plan CAPE v3, section 2): the exact v2.1 native module copied to
snapshots/v21 before any v3 change (sha256 recorded in snapshots/v21/FROZEN_V21.json and checked here).

The module is loaded from its own path under its original init name. Inside one process it shares
pybind11's exception translators with cape._cape_native (same C++ exception names), so an exception may
surface as the other module's Python class; the worker maps failures by class *name*
(cape/worker.py::_status_for_exception), which is unaffected. Streams are decoded with the original
PyPI decoder exactly like every CAPE row.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from cape.adapters.base import AdapterUnavailable
from cape.adapters.cape_native import NATIVE_KEYS, CapeNativeAdapter

ROOT = Path(__file__).resolve().parents[2]
FROZEN_DIR = ROOT / "snapshots" / "v21"
V3_ONLY_KEYS = {
    "regime_gate", "rc_fixing", "rc_max_cc", "rc_transitions_total", "rc_transitions_per_component", "rc_max_states",
    "repair", "repair_max_r", "repair_max_pool", "repair_attempts", "repair_transitions_total",
    "repair_transitions_per_attempt", "repair_max_states",
}
_MODULE = None


def frozen_record() -> dict:
    return json.loads((FROZEN_DIR / "FROZEN_V21.json").read_text(encoding="utf-8"))


def load_frozen_module():
    global _MODULE
    if _MODULE is not None:
        return _MODULE
    try:
        rec = frozen_record()
        path = FROZEN_DIR / rec["file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, KeyError, ValueError) as exc:
        raise AdapterUnavailable(f"frozen v2.1 module unavailable: {exc}") from exc
    if digest != rec["sha256"]:
        raise AdapterUnavailable(f"frozen v2.1 module modified: sha256 {digest[:12]} != {rec['sha256'][:12]}")
    spec = importlib.util.spec_from_file_location("_cape_native", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _MODULE = mod
    return mod


class CapeFrozenV21Adapter(CapeNativeAdapter):
    adapter_name = "cape_frozen_v21"

    def __init__(self, method_id, options=None, threads=1, base_options: dict | None = None):
        super().__init__(method_id, options, threads, base_options)
        bad = set(self.native_options) & V3_ONLY_KEYS
        if bad:
            raise ValueError(f"{method_id}: v3-only option(s) {sorted(bad)} are not available in the frozen v2.1 module")
        mask = self.native_options.get("impl_mask", -1)
        if mask is not None and int(mask) > 31:
            raise ValueError(f"{method_id}: impl_mask {mask} uses v3 bits; the frozen v2.1 module knows bits 0..31")
        assert set(self.native_options) <= NATIVE_KEYS

    def _modules(self):
        try:
            import crackle

            from cape import _crackle_vendor
        except ImportError as exc:
            raise AdapterUnavailable(f"native modules unavailable: {exc}") from exc
        return load_frozen_module(), _crackle_vendor, crackle

    def availability(self) -> dict:
        """File + checksum only: the module is loaded on the first encode, so availability tables never load it
        into a process that does not measure it (see the module docstring)."""
        try:
            rec = frozen_record()
            path = FROZEN_DIR / rec["file"]
            ok = hashlib.sha256(path.read_bytes()).hexdigest() == rec["sha256"]
            import crackle  # noqa: F401

            from cape import _crackle_vendor  # noqa: F401
        except (OSError, KeyError, ValueError, ImportError) as exc:
            return {"status": "UNAVAILABLE_BUILD", "version": None, "reason": str(exc)}
        if not ok:
            return {"status": "UNAVAILABLE_BUILD", "version": None, "reason": "frozen v2.1 module checksum mismatch"}
        return {"status": "AVAILABLE", "version": self.version(), "reason": None}

    def version(self) -> str:
        try:
            sha = frozen_record()["sha256"][:12]
        except (OSError, KeyError, ValueError):
            sha = "missing"
        return f"cape v2.1 frozen binary (sha256 {sha})"
