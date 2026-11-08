"""Public API: compress 3D label volumes into standard Crackle streams with CAPE pin selection.

    import numpy as np, crackle, cape.api as cape
    labels = np.load("segmentation.npy")          # 2D/3D unsigned integer labels, indexed like crackle: [x, y, z]
    stream = cape.compress(labels)                # bytes: an ordinary Crackle v1 stream (PINS label format)
    assert np.array_equal(crackle.decompress(stream), labels)   # the unmodified upstream decoder reads it

The defaults are the evaluated encoder of the final experiment (method `cape_q1_fast_m0`, implementation mask 6719,
markov order 0); tests/test_public_api.py checks that this function writes byte-identical streams to that method.
Command line:  python -m cape.api input.npy output.ckl [--zyx] [--bounds] [--threads N]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

__all__ = ["compress", "compress_with_info", "decompress", "EVALUATED_OPTIONS"]

# Run-level algorithm section of configs/q1_final_*.yaml (cape.config.cape_native_options) merged with the method
# options of cape_q1_fast_m0 in configs/q1_methods.yaml. Keep in sync; the test compares the two byte for byte.
EVALUATED_OPTIONS: dict = {
    "candidate_policy": "depth_bounded_complete_windows",
    "reduce_equal": True, "reduce_subset": True, "reduce_singleton": True,
    "dual_scale": 1048576,
    "exact_max_cc": 20, "exact_max_transitions_per_component": 50_000_000, "exact_max_transitions_total": 200_000_000,
    "exact_memory_mib": 64,
    "local_checks_per_component": 10_000, "local_checks_total": 1_000_000,
    "background_policy": "min_current_serialized_cost",
    "memory_cap_bytes": 20 * (1 << 30),
    "markov_model_order": 0,
    "format_policy": "same_as_stock",
    "selector": "cape",
    "depth_policy": "fixed_depth_width",
    "certificate": "off",
    "impl_mask": 6719,
}

_INFO_KEYS = ("label_format", "label_bytes", "pins_total_bytes", "P", "Q", "background_label", "regime_w_D",
              "payload_ub_bytes", "ub_bytes", "lb_bytes", "label_lb_bytes", "certificate_mode", "certificate_scope",
              "certificate_dual_feasible", "encode_core_ns")


def _native():
    try:
        from cape import _cape_native
    except ImportError as exc:  # pragma: no cover - depends on the local build
        raise ImportError("the CAPE native module is not built: run `python scripts/build_native.py` "
                          "(see README.md, 'Install')") from exc
    return _cape_native


def _crackle_layout(labels) -> np.ndarray:
    """Crackle indexes volumes as [x, y, z]; the native encoder reads that layout in Fortran order."""
    a = np.asarray(labels)
    if a.ndim == 2:
        a = a[:, :, np.newaxis]
    if a.ndim != 3:
        raise ValueError(f"expected a 2D or 3D label array, got shape {a.shape}")
    if a.dtype == np.bool_:
        a = a.astype(np.uint8)
    if a.dtype.kind != "u":
        raise TypeError(f"unsupported dtype {a.dtype}: CAPE encodes unsigned integer labels (uint8/16/32/64); "
                        "convert or view signed labels as unsigned first")
    if a.dtype.byteorder == ">":
        a = a.astype(a.dtype.newbyteorder("<"))
    return np.asfortranarray(a)


def compress_with_info(labels, *, bounds: bool = False, threads: int = 1, **options) -> tuple[bytes, dict]:
    """Return (stream, info). With bounds=True the encoder also computes a lower bound on the label section
    (same stream, all depth regimes, backgrounds and count widths): info['label_lb_bytes'] <= info['label_bytes'].
    Extra keyword options override EVALUATED_OPTIONS (advanced; changes the evaluated configuration)."""
    opts = dict(EVALUATED_OPTIONS)
    opts.update(options)
    if bounds:
        opts["certificate"] = "all_regimes"
    opts["parallel"] = int(threads)
    buf, diag = _native().encode(_crackle_layout(labels), opts)
    info = {k: diag[k] for k in _INFO_KEYS if k in diag}
    info["total_bytes"] = len(buf)
    if bounds and "label_lb_bytes" in diag and diag.get("label_bytes"):
        gap = diag["label_bytes"] - diag["label_lb_bytes"]
        info["label_gap_bytes"] = gap
        info["label_gap_pct_of_label_section"] = 100.0 * gap / diag["label_bytes"]
        info["label_gap_pct_of_stream"] = 100.0 * gap / len(buf)
    return bytes(buf), info


def compress(labels, *, threads: int = 1) -> bytes:
    """Compress labels ([x, y, z], unsigned integers) into a Crackle v1 stream with CAPE pin selection."""
    return compress_with_info(labels, threads=threads)[0]


def decompress(stream: bytes, *, threads: int = 1) -> np.ndarray:
    """Decode with the unmodified upstream decoder (PyPI crackle-codec); returns the [x, y, z] array."""
    import crackle

    return crackle.decompress(stream, parallel=threads)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m cape.api", description="Compress a .npy label volume with CAPE")
    ap.add_argument("input", help=".npy file with a 2D/3D unsigned integer label array indexed [x, y, z]")
    ap.add_argument("output", help="output Crackle stream (.ckl)")
    ap.add_argument("--bounds", action="store_true", help="also compute the label-section lower bound")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--zyx", action="store_true", help="the .npy array is stored as [z, y, x] (transposed on load)")
    ap.add_argument("--no-verify", action="store_true", help="skip the decode-and-compare check")
    a = ap.parse_args(argv)
    labels = np.load(a.input, allow_pickle=False)
    if a.zyx:
        labels = labels.T
    stream, info = compress_with_info(labels, bounds=a.bounds, threads=a.threads)
    Path(a.output).write_bytes(stream)
    if not a.no_verify:
        info["lossless_verified_with_upstream_decoder"] = bool(np.array_equal(decompress(stream), labels))
    info["input_bytes"] = int(labels.nbytes)
    json.dump(info, sys.stdout, indent=2, default=str)
    print()
    return 0 if info.get("lossless_verified_with_upstream_decoder", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
