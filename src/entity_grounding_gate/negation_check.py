"""Detect 'no issues with X' / 'no findings for X' phrases and assert truth."""
from __future__ import annotations
import re

_NEGATION = re.compile(
    r"no\s+(?:issues|findings|violations|problems)\s+(?:with|for|in)\s+`([^`]+)`",
    re.IGNORECASE,
)


def find_negated_entities(narrative_text: str) -> list[str]:
    return _NEGATION.findall(narrative_text)


def check_negations(narrative_text: str, findings: list[dict]) -> list[dict]:
    """Return list of false-negation violations (entity claimed clean but has findings)."""
    out: list[dict] = []
    for entity in find_negated_entities(narrative_text):
        hits = [
            f for f in findings
            if entity in f.get("principal", "") or entity in f.get("databases", [])
        ]
        if hits:
            out.append({"entity": entity, "hit_count": len(hits)})
    return out
