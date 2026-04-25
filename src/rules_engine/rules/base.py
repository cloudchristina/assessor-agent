"""Rule abstract class. Each rule = one module + one test file."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterable
from src.shared.models import Finding, UARRow


@dataclass(frozen=True)
class RuleContext:
    run_id: str
    now: object  # datetime, kept loose for test injectability
    config: dict[str, object] = field(default_factory=dict)


class Rule(ABC):
    rule_id: str
    severity: str
    ism_controls: list[str]
    description: str

    @abstractmethod
    def evaluate(self, rows: Iterable[UARRow], ctx: RuleContext) -> list[Finding]:
        ...
