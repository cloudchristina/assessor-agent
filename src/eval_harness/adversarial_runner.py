"""Adversarial case runner — stub for Task 2.1; full runner added in Task 2.2."""
from __future__ import annotations

import json
from pathlib import Path

from src.shared.models import AdversarialCase

_ADVERSARIAL_DIR = Path(__file__).parent.parent.parent / "evals" / "adversarial"


def load_all_adversarial_cases() -> list[AdversarialCase]:
    """Load and validate all adversarial case JSON files (top-level only, not fixtures/)."""
    return [
        AdversarialCase.model_validate(json.loads(p.read_text()))
        for p in sorted(_ADVERSARIAL_DIR.glob("*.json"))
    ]
