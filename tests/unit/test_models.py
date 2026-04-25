from datetime import datetime
import pytest
from pydantic import ValidationError
from src.shared.models import (
    UARRow,
    ExtractManifest,
    Finding,
    RulesEngineOutput,
    NarrativeReport,
    NarrativeFindingRef,
    ThemeCluster,
    JudgeScore,
    TriageDecision,
)


def test_uar_row_accepts_minimal_valid():
    row = UARRow(
        login_name="alice",
        login_type="SQL_LOGIN",
        login_create_date=datetime(2024, 1, 1),
        last_active_date=None,
        server_roles=[],
        database="appdb (sql01)",
        mapped_user_name=None,
        user_type=None,
        default_schema=None,
        db_roles=[],
        explicit_read=False,
        explicit_write=False,
        explicit_exec=False,
        explicit_admin=False,
        access_level="Unknown",
        grant_counts={},
        deny_counts={},
    )
    assert row.login_name == "alice"


def test_uar_row_rejects_unknown_login_type():
    with pytest.raises(ValidationError):
        UARRow.model_validate({
            "login_name": "alice",
            "login_type": "INVALID",
            "login_create_date": "2024-01-01T00:00:00",
            "last_active_date": None,
            "server_roles": [],
            "database": "x",
            "mapped_user_name": None,
            "user_type": None,
            "default_schema": None,
            "db_roles": [],
            "explicit_read": False,
            "explicit_write": False,
            "explicit_exec": False,
            "explicit_admin": False,
            "access_level": "Unknown",
            "grant_counts": {},
            "deny_counts": {},
        })


def test_extract_manifest_round_trip():
    m = ExtractManifest(
        run_id="run_2026-04-25_weekly",
        cadence="weekly",
        extracted_at=datetime(2026, 4, 25, 9, 0),
        extractor_version="0.1.0",
        servers_processed=["sql01"],
        databases_processed=["appdb"],
        row_count=10,
        row_ids_sha256="0" * 64,
        schema_version="1",
    )
    assert m.model_dump_json()
    assert ExtractManifest.model_validate_json(m.model_dump_json()) == m


def test_finding_id_format_validated():
    f = Finding(
        finding_id="F-run_2026-04-25_weekly-R1-0001",
        run_id="run_2026-04-25_weekly",
        rule_id="R1",
        severity="CRITICAL",
        ism_controls=["ISM-1546"],
        principal="alice",
        databases=["appdb"],
        evidence={"login_type": "SQL_LOGIN"},
        detected_at=datetime(2026, 4, 25),
    )
    assert f.severity == "CRITICAL"


def test_rules_engine_output_summary_consistent():
    out = RulesEngineOutput(
        run_id="run_2026-04-25_weekly",
        findings=[],
        summary={"R1": 0, "CRITICAL": 0},
        principals_scanned=0,
        databases_scanned=0,
    )
    assert out.findings == []


def test_narrative_report_minimal():
    r = NarrativeReport(
        run_id="run_2026-04-25_weekly",
        executive_summary="No findings.",
        theme_clusters=[],
        finding_narratives=[],
        cycle_over_cycle=None,
        total_findings=0,
        model_id="claude-sonnet-4-6",
        generated_at=datetime(2026, 4, 25),
    )
    assert r.total_findings == 0


def test_judge_score_bounds():
    s = JudgeScore(
        faithfulness=0.95, completeness=0.9, fabrication=0.0,
        reasoning="ok", model_id="claude-haiku-4-5",
    )
    assert 0 <= s.faithfulness <= 1
