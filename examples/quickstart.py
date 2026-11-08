"""CAPE quick start: compress a label volume, decode it with the unmodified upstream Crackle decoder, and compare
with upstream Crackle (flat and pins) on the same volume.

    python examples/quickstart.py                       # synthetic 128^3 volume
    python examples/quickstart.py labels.npy            # your volume, indexed [x, y, z] (crackle convention)
    python examples/quickstart.py labels.npy --zyx      # your volume stored as [z, y, x]

Single run, wall-clock timing on one thread: an illustration, not a benchmark (the benchmark is tools/q1_pipeline.py).
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import crackle  # noqa: E402

import cape.api as cape  # noqa: E402


def synthetic(n=128, seed=0):
    """Blocky labels with smooth boundaries: a stand-in for a neuron segmentation."""
    rng = np.random.default_rng(seed)
    seeds = rng.integers(0, n, size=(400, 3))
    g = np.stack(np.meshgrid(*(np.arange(0, n, 4),) * 3, indexing="ij"), -1).reshape(-1, 3)
    lab = np.argmin(((g[:, None, :] - seeds[None]) ** 2).sum(-1), 1).astype(np.uint32) + 1
    lab = lab.reshape((n // 4,) * 3)
    return np.kron(lab, np.ones((4, 4, 4), np.uint32))


def timed(fn):
    t = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("npy", nargs="?")
    ap.add_argument("--zyx", action="store_true", help="the .npy file is stored as [z, y, x]")
    a = ap.parse_args()
    labels = np.load(a.npy, allow_pickle=False) if a.npy else synthetic()
    if a.zyx:
        labels = labels.T
    print(f"volume {labels.shape} {labels.dtype}, {labels.nbytes / 2**20:.1f} MiB, {len(np.unique(labels))} labels")

    (stream, info), t_cape = timed(lambda: cape.compress_with_info(labels, bounds=True))
    assert np.array_equal(crackle.decompress(stream), labels), "not lossless"
    print(f"CAPE            {len(stream):>10,d} B  {t_cape:7.3f} s  lossless (upstream decoder)")
    print(f"  label section {info['label_bytes']:,d} B of {info['total_bytes']:,d} B; lower bound "
          f"{info['label_lb_bytes']:,d} B -> gap <= {info['label_gap_pct_of_label_section']:.2f}% of the label section")
    for name, kw in [("Crackle flat", {}), ("Crackle pins", {"allow_pins": 1})]:
        s, t = timed(lambda: crackle.compress(labels, parallel=1, **kw))
        print(f"{name:15s} {len(s):>10,d} B  {t:7.3f} s")


if __name__ == "__main__":
    main()
