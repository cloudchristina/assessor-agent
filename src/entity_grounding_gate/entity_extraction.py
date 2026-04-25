"""Lightweight entity extraction via regex. Tuned for our narrative shape, not NER-grade."""
from __future__ import annotations
import re

_BACKTICK = re.compile(r"`([A-Za-z0-9_.\-]+)`")
_ISM = re.compile(r"\b(ISM-\d{3,4})\b")
_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_NUM = re.compile(r"(?<![A-Za-z0-9_])(\d+)(?![A-Za-z0-9_])")


def extract_entities(text: str) -> dict[str, set]:
    backticked = set(_BACKTICK.findall(text))
    # heuristic split: anything containing 'db' is a DB name; else principal
    dbs = {b for b in backticked if "db" in b.lower() or "_db" in b.lower()}
    principals = backticked - dbs
    return {
        "principals": principals,
        "databases": dbs,
        "controls": set(_ISM.findall(text)),
        "dates": set(_DATE.findall(text)),
        "numbers": {int(n) for n in _NUM.findall(text)},
    }
