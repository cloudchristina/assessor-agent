"""Pydantic v2 boundary models — all I/O contracts in one place."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class UARRow(BaseModel):
    model_config = ConfigDict(frozen=True)
    login_name: str
    login_type: Literal["SQL_LOGIN", "WINDOWS_LOGIN", "WINDOWS_GROUP"]
    login_create_date: datetime
    last_active_date: datetime | None
    server_roles: list[str]
    database: str
    mapped_user_name: str | None
    user_type: str | None
    default_schema: str | None
    db_roles: list[str]
    explicit_read: bool
    explicit_write: bool
    explicit_exec: bool
    explicit_admin: bool
    access_level: Literal["Admin", "Write", "ReadOnly", "Unknown"]
    grant_counts: dict[str, int]
    deny_counts: dict[str, int]


class ExtractManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_id: str
    cadence: Literal["weekly", "monthly"]
    extracted_at: datetime
    extractor_version: str
    servers_processed: list[str]
    databases_processed: list[str]
    row_count: int
    row_ids_sha256: str
    schema_version: str


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True)
    finding_id: str
    run_id: str
    rule_id: Literal["R1", "R2", "R3", "R4", "R5", "R6"]
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    ism_controls: list[str]
    principal: str
    databases: list[str]
    evidence: dict[str, Any]
    detected_at: datetime


class RulesEngineOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_id: str
    findings: list[Finding]
    summary: dict[str, int]
    principals_scanned: int
    databases_scanned: int


class NarrativeFindingRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    finding_id: str
    group_theme: str | None
    remediation: str
    ism_citation: str


class ThemeCluster(BaseModel):
    model_config = ConfigDict(frozen=True)
    theme: str
    finding_ids: list[str]
    summary: str


class NarrativeReport(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_id: str
    executive_summary: str
    theme_clusters: list[ThemeCluster]
    finding_narratives: list[NarrativeFindingRef]
    cycle_over_cycle: str | None
    total_findings: int
    model_id: str
    generated_at: datetime


class JudgeScore(BaseModel):
    model_config = ConfigDict(frozen=True)
    faithfulness: float
    completeness: float
    fabrication: float
    reasoning: str
    model_id: str


class TriageDecision(BaseModel):
    model_config = ConfigDict(frozen=True)
    finding_id: str
    reviewer_sub: str
    decision: Literal["confirmed_risk", "false_positive", "accepted_exception", "escalated"]
    rationale: str
    decided_at: datetime


class ExpectedFinding(BaseModel):
    model_config = ConfigDict(frozen=True)
    rule_id: Literal["R1", "R2", "R3", "R4", "R5", "R6"]
    principal: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]


class GoldenCase(BaseModel):
    model_config = ConfigDict(frozen=True)
    case_id: str
    input_csv: str
    expected_findings: list[ExpectedFinding]
    expected_counts: dict[str, int]
    must_mention: list[str]
    must_not_mention: list[str]
    notes: str | None = None


class AdversarialCase(BaseModel):
    model_config = ConfigDict(frozen=True)
    case_id: str
    description: str
    # The attack: either an in-zip CSV path OR an inline-generated programme.
    input_csv: str | None = None
    generator_fn: str | None = None  # dotted path, e.g. "evals.adversarial.gen.prompt_injection"
    expected_outcome: Literal[
        "citation_gate_fail",
        "narrative_no_findings",
        "rules_engine_error",
        "judge_pass",
        "agent_quotes_verbatim",
    ]
    expected_assertions: list[str]  # human-readable assertions, checked by adversarial_runner
