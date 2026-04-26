"""Load + validate golden case JSON files."""
from __future__ import annotations
import json
from pathlib import Path
from src.shared.models import GoldenCase

_GOLDEN_DIR = Path(__file__).parent.parent.parent / "evals" / "golden"


def load_all_golden_cases() -> list[GoldenCase]:
    return [
        GoldenCase.model_validate_json(p.read_text())
        for p in sorted(_GOLDEN_DIR.glob("*.json"))
    ]


def load_case_by_id(case_id: str) -> GoldenCase:
    for p in _GOLDEN_DIR.glob("*.json"):
        case = GoldenCase.model_validate_json(p.read_text())
        if case.case_id == case_id:
            return case
    raise FileNotFoundError(case_id)
