"""Provenance hashes (spec sections 27, 30, 31): source tree, configs, inputs."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Output roots; acceptance tests point them at an isolated directory (spec 38: fault-injection
# runs live outside paper results).
RESULTS_ROOT = Path(os.environ.get("CAPE_RESULTS_ROOT", ROOT / "results"))
RELEASE_ROOT = Path(os.environ.get("CAPE_RELEASE_ROOT", ROOT / "release"))
FREEZE_ROOT = Path(os.environ.get("CAPE_FREEZE_ROOT", ROOT / "configs" / "frozen"))
METHODS_FILE = Path(os.environ.get("CAPE_METHODS_FILE", ROOT / "configs" / "methods.yaml"))


def active_test_hooks() -> dict:
    """Fault-injection hooks used only by the acceptance tests; recorded in every run manifest."""
    keys = ("CAPE_TEST_INTERRUPT_AFTER", "CAPE_TEST_FAIL_FIGURE", "CAPE_METHODS_FILE", "CAPE_RESULTS_ROOT")
    return {k: os.environ[k] for k in keys if k in os.environ}

SOURCE_GLOBS = ["cape/**/*.py", "cpp/**/*.hpp", "cpp/**/*.cpp", "scripts/*.py", "configs/*.yaml",
                "schemas/*.json", "tests/**/*.py", "CMakeLists.txt", "pyproject.toml", "requirements.in",
                "requirements.lock", "sources.lock.json", "run_all.py", "run_experiment.cmd",
                "run_experiment.ps1", "run_experiment.sh"]


def source_files(root: Path = ROOT) -> list[Path]:
    files: set[Path] = set()
    for pattern in SOURCE_GLOBS:
        files.update(p for p in root.glob(pattern) if p.is_file() and "__pycache__" not in p.parts)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def source_tree_hash(root: Path = ROOT) -> str:
    h = hashlib.sha256()
    for p in source_files(root):
        h.update(p.relative_to(root).as_posix().encode())
        h.update(b"\0")
        h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def json_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def resume_key(input_hash: str, source_hash: str, config_hash: str, method_id: str, wrapper: str, panel: str,
               repeat: int) -> str:
    return "|".join([input_hash, source_hash, config_hash, method_id, wrapper, panel, str(repeat)])


def task_id_from_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:20]
