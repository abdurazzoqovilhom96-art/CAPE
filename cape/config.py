"""Typed configuration schema (spec section 26): unknown keys are errors, every value is
type-checked, defaults are explicit, and the validated config has a canonical hash.

A run config (configs/{smoke,pilot,development,benchmark,oracle,roi}.yaml) selects methods
from configs/methods.yaml and datasets through a manifest.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Field:
    kind: Any  # python type, tuple of types, or "list:<type>"
    required: bool = False
    default: Any = None
    choices: tuple | None = None
    check: Callable[[Any], bool] | None = None
    doc: str = ""


def _section(fields: dict) -> dict:
    return {"__section__": True, **fields}


def _pos(v) -> bool:
    return v > 0


def _nonneg(v) -> bool:
    return v >= 0


RUN_SCHEMA = {
    "schema_version": Field(int, required=True, choices=(1,)),
    "project": Field(str, required=True, choices=("CAPE-Pins",)),
    "seed": Field(int, default=20261105),
    "mode": Field(str, required=True, choices=("smoke", "pilot", "development", "benchmark", "oracle", "roi")),
    "description": Field(str, default=""),
    "input": _section({
        "manifest": Field(str, required=True),
        "canonical_axes": Field(str, default="ZYX", choices=("ZYX",)),
        "preserve_ids": Field(bool, default=True, choices=(True,)),
        "allow_synthetic_for_real": Field(bool, default=False, choices=(False,)),
        "splits": Field("list:str", default=["development"]),
        "require_real_data": Field(bool, default=False),
    }),
    "algorithm": _section({
        "candidate_policy": Field(str, default="depth_bounded_complete_windows",
                                  choices=("depth_bounded_complete_windows", "maximal_runs_only")),
        "reductions": Field("list:str", default=["equal_coverage", "subset", "singleton_dominance"]),
        "online_dual": Field(str, default="fixed_point_ascent", choices=("fixed_point_ascent",)),
        "dual_scale": Field(int, default=1048576, check=_pos),
        "exact_max_cc": Field(int, default=20, check=lambda v: 0 <= v <= 30),
        "exact_max_transitions_per_component": Field(int, default=50_000_000, check=_nonneg),
        "exact_max_transitions_total": Field(int, default=200_000_000, check=_nonneg),
        "exact_memory_mib": Field(int, default=64, check=_pos),
        "local_checks_per_component": Field(int, default=10_000, check=_nonneg),
        "local_checks_total": Field(int, default=1_000_000, check=_nonneg),
        "count_policy": Field(str, default="safe_then_compact", choices=("safe_then_compact",)),
        "depth_policy": Field(str, default="full_width_first", choices=("full_width_first", "fixed_depth_width")),
        "background_policy": Field(str, default="min_current_serialized_cost",
                                   choices=("min_current_serialized_cost", "stock")),
        "deterministic": Field(bool, default=True, choices=(True,)),
    }),
    "benchmark": _section({
        "threads": Field(int, default=1, check=_pos),
        "concurrent_timed_jobs": Field(int, default=1, choices=(1,)),
        "warmups": Field(int, default=1, check=_nonneg),
        "repeats": Field(int, default=7, check=_pos),
        "min_batch_ms": Field(int, default=200, check=_nonneg),
        "small_task_ms": Field(int, default=50, check=_nonneg),
        "task_timeout_s": Field(int, default=600, check=_pos),
        "process_memory_gib": Field((int, float), default=20, check=_pos),
        "max_total_working_memory_gib": Field((int, float), default=24, check=_pos),
        "memory_profile_separate": Field(bool, default=True),
        "verify_every_result": Field(bool, default=True, choices=(True,)),
        "external_wrappers": Field("list:str", default=["none", "zstd3"]),
        "pin_timing_cpu": Field(bool, default=True),
        "disk_cap_gib": Field((int, float), default=20, check=_pos),
        "min_free_disk_gib": Field((int, float), default=2, check=_pos),
    }),
    "outputs": _section({
        "root": Field(str, default="results"),
        "write_bitstreams": Field(bool, default=True),
        "write_decoded_arrays": Field(bool, default=False),
        "archive_raw_metrics": Field(bool, default=True),
        "paper_assets": Field(bool, default=True),
        "live_plot_every": Field(int, default=10, check=_pos),
        "include_bitstreams_in_release": Field(bool, default=False),
    }),
    "methods": Field("list:str", required=True),
    "panels": Field("list:str", default=["A", "B"]),
    "primary": _section({
        "new": Field(str, default="cape_m0"),
        "baseline": Field(str, default="crackle_pins_opt_m0"),
    }),
    "stats": _section({
        "bootstrap_resamples": Field(int, default=10_000, check=_pos),
        "seed": Field(int, default=20261105),
        "cluster_by": Field(str, default="macroblock_id", choices=("macroblock_id", "source_id", "sample_id")),
    }),
    "oracle": _section({
        "enabled": Field(bool, default=False),
        "max_cc": Field(int, default=60, check=_pos),
        "max_components": Field(int, default=200, check=_pos),
        "time_limit_s": Field((int, float), default=20, check=_pos),
    }),
    "roi": _section({
        "enabled": Field(bool, default=False),
        "chunk_xyz": Field("list:int", default=[128, 128, 64]),
        "queries_per_sample": Field(int, default=3, check=_pos),
    }),
}

METHOD_SCHEMA = {
    "adapter": Field(str, required=True),
    "options": Field(dict, default={}),
    "family": Field(str, required=True),
    "categories": Field("list:str", default=[]),
    "panels": Field("list:str", default=["B"]),
    "wrappable": Field(bool, default=False),
    "role": Field(str, default="comparator", choices=("new", "baseline", "internal", "comparator", "reference")),
    "description": Field(str, default=""),
    "citation": Field(str, default=""),
    # v2.1: experimental methods run only when a config lists them by name; reports never show them as
    # the winner or as the "new" method
    "experimental": Field(bool, default=False),
}

KNOWN_REDUCTIONS = ("equal_coverage", "subset", "singleton_dominance")
KNOWN_PANELS = ("A", "B", "C")
KNOWN_WRAPPERS = ("none", "zstd3", "zstd9")


def _type_ok(kind, value) -> bool:
    if isinstance(kind, str) and kind.startswith("list:"):
        if not isinstance(value, list):
            return False
        inner = kind[5:]
        for v in value:
            if inner == "str" and not isinstance(v, str):
                return False
            if inner in ("int", "float") and (isinstance(v, bool) or not isinstance(v, (int, float))):
                return False
            if inner == "int" and not isinstance(v, int):
                return False
        return True
    if kind is int:
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == (int, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, kind)


def validate(data: Any, schema: dict, where: str = "config") -> dict:
    if not isinstance(data, dict):
        raise ConfigError(f"{where}: expected a mapping")
    unknown = sorted(set(data) - {k for k in schema if k != "__section__"})
    if unknown:
        raise ConfigError(f"{where}: unknown key(s) {unknown}")
    out = {}
    for key, spec in schema.items():
        if key == "__section__":
            continue
        path = f"{where}.{key}"
        if isinstance(spec, dict):
            out[key] = validate(data.get(key, {}), spec, path)
            continue
        if key not in data:
            if spec.required:
                raise ConfigError(f"{path}: required")
            out[key] = copy.deepcopy(spec.default)
            continue
        value = data[key]
        if not _type_ok(spec.kind, value):
            raise ConfigError(f"{path}: expected {spec.kind}, got {type(value).__name__}")
        if spec.choices is not None and value not in spec.choices:
            raise ConfigError(f"{path}: {value!r} not in {spec.choices}")
        if spec.check is not None and not spec.check(value):
            raise ConfigError(f"{path}: invalid value {value!r}")
        out[key] = copy.deepcopy(value)
    return out


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _load_yaml(path: Path) -> Any:
    import yaml

    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_methods(path: Path | None = None) -> dict:
    from cape.provenance import METHODS_FILE

    path = path or METHODS_FILE
    raw = _load_yaml(path)
    if not isinstance(raw, dict) or set(raw) - {"schema_version", "methods"} or raw.get("schema_version") != 1:
        raise ConfigError(f"{path}: expected keys schema_version: 1 and methods")
    methods = {}
    for mid, spec in raw["methods"].items():
        m = validate(spec, METHOD_SCHEMA, f"methods.{mid}")
        bad = set(m["panels"]) - set(KNOWN_PANELS)
        if bad:
            raise ConfigError(f"methods.{mid}.panels: unknown {sorted(bad)}")
        methods[mid] = m
    return methods


def load_run_config(path: str | Path, methods: dict | None = None) -> dict:
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise ConfigError(f"config file not found: {path}")
    cfg = validate(_load_yaml(path), RUN_SCHEMA, path.name)
    methods = methods if methods is not None else load_methods()
    missing = [m for m in cfg["methods"] if m not in methods]
    if missing:
        raise ConfigError(f"{path.name}.methods: not in configs/methods.yaml: {missing}")
    bad = set(cfg["algorithm"]["reductions"]) - set(KNOWN_REDUCTIONS)
    if bad:
        raise ConfigError(f"{path.name}.algorithm.reductions: unknown {sorted(bad)}")
    bad = set(cfg["panels"]) - set(KNOWN_PANELS)
    if bad:
        raise ConfigError(f"{path.name}.panels: unknown {sorted(bad)}")
    bad = set(cfg["benchmark"]["external_wrappers"]) - set(KNOWN_WRAPPERS)
    if bad:
        raise ConfigError(f"{path.name}.benchmark.external_wrappers: unknown {sorted(bad)}")
    for key in ("new", "baseline"):
        if cfg["primary"][key] not in methods:
            raise ConfigError(f"{path.name}.primary.{key}: unknown method {cfg['primary'][key]}")
    cfg["_path"] = str(path)
    cfg["_hash"] = canonical_hash({k: v for k, v in cfg.items() if not k.startswith("_")})
    cfg["_methods_hash"] = canonical_hash({m: methods[m] for m in cfg["methods"]})
    return cfg


def cape_native_options(cfg: dict) -> dict:
    """Map the algorithm section to _cape_native.encode options."""
    a = cfg["algorithm"]
    red = set(a["reductions"])
    return {
        "candidate_policy": a["candidate_policy"],
        "reduce_equal": "equal_coverage" in red,
        "reduce_subset": "subset" in red,
        "reduce_singleton": "singleton_dominance" in red,
        "dual_scale": a["dual_scale"],
        "exact_max_cc": a["exact_max_cc"],
        "exact_max_transitions_per_component": a["exact_max_transitions_per_component"],
        "exact_max_transitions_total": a["exact_max_transitions_total"],
        "exact_memory_mib": a["exact_memory_mib"],
        "local_checks_per_component": a["local_checks_per_component"],
        "local_checks_total": a["local_checks_total"],
        "depth_policy": a["depth_policy"],
        "background_policy": a["background_policy"],
        "memory_cap_bytes": int(cfg["benchmark"]["process_memory_gib"] * (1 << 30)),
        "parallel": cfg["benchmark"]["threads"],
    }
