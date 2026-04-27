"""Tests for scripts/generate_golden.py synthetic case generator."""
from __future__ import annotations

import json
import subprocess
import sys


def test_generate_synthetic_case_500_principals(tmp_path):
    out_csv = tmp_path / "case.csv"
    out_json = tmp_path / "case.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.generate_golden",
            "--scenario=synth_500_principals",
            "--out-csv",
            str(out_csv),
            "--out-json",
            str(out_json),
        ],
        check=True,
    )
    assert out_csv.exists()
    assert out_json.exists()
    spec = json.loads(out_json.read_text())
    assert spec["case_id"] == "synth_500_principals"
    # 500-row scenario should produce >50 findings (volume stress)
    assert sum(spec["expected_counts"].values()) > 50
