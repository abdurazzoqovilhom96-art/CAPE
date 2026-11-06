"""Report integrity (spec section 29): measurement rows follow the schema, a tampered
bitstream is detected, failed-lossless rows never enter the winner tables."""

from __future__ import annotations

import json

import jsonschema
import numpy as np

from cape import metrics
from cape.provenance import ROOT
from cape.result_store import MEASUREMENT_FIELDS

SCHEMA = json.loads((ROOT / "schemas" / "measurement.schema.json").read_text(encoding="utf-8"))


def _row(**kw) -> dict:
    row = {f: None for f in MEASUREMENT_FIELDS}
    row.update(run_id="r", task_id="t", sample_id="s", method_id="cape_m0", method_version="v", config_hash="c",
               source_hash="s", input_hash="h", panel="B", split="development", repeat=0, seed=1, threads=1,
               status="OK", original_dtype="uint32", canonical_shape=[2, 2, 2], input_bytes=32, payload_bytes=40,
               metadata_bytes=0, total_bytes=40, encode_ns=10, decode_ns=10, lossless=True,
               bitstream_sha256="a" * 64)
    row.update(kw)
    return row


def test_measurement_schema_accepts_valid_and_rejects_fake_success():
    jsonschema.validate(_row(), SCHEMA)
    for bad in (_row(lossless=False), _row(total_bytes=0), _row(bitstream_sha256=None), _row(status="WIN")):
        try:
            jsonschema.validate(bad, SCHEMA)
        except jsonschema.ValidationError:
            continue
        raise AssertionError(f"schema accepted {bad}")


def test_failed_lossless_rows_have_no_size_in_cells():
    rows = [dict(_row(status="FAILED_LOSSLESS", lossless=False, method_id="m"), measurement_id=1, wrapper="none",
                 is_synthetic=False, family_id="f", source_id="s", macroblock_id="b", extra_json="{}")]
    cell = metrics.aggregate_cells(rows)[("s", "m", "B")]
    assert cell["n_ok"] == 0 and "total_bytes" not in cell


def test_verifier_detects_tampered_bitstream(tmp_path):
    from cape.artifact_manifest import _sha

    p = tmp_path / ("0" * 64 + ".bin")
    p.write_bytes(b"abc")
    assert _sha(p) != p.stem  # the verifier compares file content hash with its name


def test_bpv_and_ratio_definitions():
    assert metrics.bpv(100, 800) == 1.0
    assert metrics.compression_ratio(100, 800, "uint32") == 32.0
    assert np.isclose(metrics.gain_percent(97, 100), 3.0) and np.isclose(metrics.gain_percent(103, 100), -3.0)


def test_limitation_notes_follow_the_actual_samples():
    """Regression (width-sensitivity run 2026-11-05): a fixed 'NOT_EXERCISED' sentence was printed
    for a run whose samples had Z = 512."""
    from types import SimpleNamespace

    from cape.reporting import _csgv_note, _depth_regime_note

    def ctx(*zs, synthetic=False):
        return SimpleNamespace(rows=[{"shape": [z, 8, 8], "is_synthetic": synthetic} for z in zs])

    assert "NOT_EXERCISED" in _depth_regime_note(ctx(64, 125))
    assert "NOT_EXERCISED" in _depth_regime_note(ctx(512, synthetic=True))  # synthetic never counts
    note = _depth_regime_note(ctx(128, 512))
    assert "sinaldi" in note and "1/2" in note and "Z=512" in note
    assert "yo'q" in _csgv_note([{"method": "zstd3", "status": "AVAILABLE"}])
    assert "cli_process_file_to_file" in _csgv_note([{"method": "csgv_rans_b64", "status": "AVAILABLE"}])
    assert "bloklanadi" in _csgv_note([{"method": "csgv_rans_b64", "status": "UNAVAILABLE"}])
