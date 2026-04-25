"""Judge system prompt. Kept in its own module so it can be imported by both
the handler and any offline eval tooling without dragging in boto3/strands."""
from __future__ import annotations


SYSTEM_PROMPT = """\
You are auditing a compliance narrative against a list of ground-truth findings.
Score:
  - faithfulness (0..1): does every claim trace to findings?
  - completeness (0..1): are all CRITICAL/HIGH findings mentioned?
  - fabrication  (0..1): how much content is unsupported (higher = more fabrication)?
Return JSON matching the JudgeScore schema. temperature=0.
"""
