"""C8 entity-grounding-gate: groundedness + negation-consistency."""
from __future__ import annotations
import json
from urllib.parse import urlparse
import boto3
from src.shared.logging import get_logger
from src.entity_grounding_gate.entity_extraction import extract_entities
from src.entity_grounding_gate.negation_check import check_negations

log = get_logger("entity-grounding-gate")
s3 = boto3.client("s3")


def _read_json(uri: str) -> dict:
    p = urlparse(uri)
    return json.loads(s3.get_object(Bucket=p.netloc, Key=p.path.lstrip("/"))["Body"].read())


def lambda_handler(event: dict, _ctx: object) -> dict:
    findings = _read_json(event["findings_s3_uri"]).get("findings", [])
    narrative = _read_json(event["narrative_s3_uri"])
    text_blob = " ".join([
        narrative.get("executive_summary", ""),
        *(c.get("summary", "") for c in narrative.get("theme_clusters", [])),
        *(n.get("remediation", "") for n in narrative.get("finding_narratives", [])),
    ])
    found = extract_entities(text_blob)
    truth_principals = {f["principal"] for f in findings}
    truth_dbs = {db for f in findings for db in f.get("databases", [])}
    truth_controls = {c for f in findings for c in f.get("ism_controls", [])}

    ungrounded = {
        "principals": sorted(found["principals"] - truth_principals),
        "databases": sorted(found["databases"] - truth_dbs),
        "controls": sorted(found["controls"] - truth_controls),
    }
    false_negations = check_negations(text_blob, findings)
    passed = not any(ungrounded.values()) and not false_negations
    log.info("grounding.gate", extra={"passed": passed})
    return {
        "gate": "entity_grounding",
        "passed": passed,
        "passed_int": 1 if passed else 0,
        "ungrounded_entities": ungrounded,
        "false_negations": false_negations,
    }
