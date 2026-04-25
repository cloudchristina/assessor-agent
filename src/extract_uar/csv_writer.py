"""Build (csv_bytes, ExtractManifest) deterministically from a list of row dicts.

Manifest hash = SHA-256 over newline-joined sorted `{login_name}||{database}`
strings — so two runs over identical rows produce identical hashes.
"""
from __future__ import annotations
import csv
import hashlib
import io
from datetime import datetime
from typing import Iterable

from src.shared.models import ExtractManifest
from src.extract_uar.csv_codec import encode_row


EXTRACTOR_VERSION = "0.1.0"
SCHEMA_VERSION = "1"

COLUMNS = [
    "login_name",
    "login_type",
    "login_create_date",
    "last_active_date",
    "server_roles",
    "database",
    "mapped_user_name",
    "user_type",
    "default_schema",
    "db_roles",
    "explicit_read",
    "explicit_write",
    "explicit_exec",
    "explicit_admin",
    "access_level",
    "grant_counts",
    "deny_counts",
]


def _row_ids_sha256(rows: Iterable[dict]) -> str:
    ids = sorted(f"{r['login_name']}||{r['database']}" for r in rows)
    h = hashlib.sha256()
    h.update("\n".join(ids).encode("utf-8"))
    return h.hexdigest()


def build_csv_and_manifest(
    rows: list[dict],
    *,
    run_id: str,
    servers: list[str],
    databases: list[str],
    cadence: str,
    extracted_at: datetime | None = None,
) -> tuple[bytes, ExtractManifest]:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(encode_row(row))
    csv_bytes = buf.getvalue().encode("utf-8")

    manifest = ExtractManifest(
        run_id=run_id,
        cadence=cadence,  # type: ignore[arg-type]
        extracted_at=extracted_at or datetime.now(),
        extractor_version=EXTRACTOR_VERSION,
        servers_processed=sorted(set(servers)),
        databases_processed=sorted(set(databases)),
        row_count=len(rows),
        row_ids_sha256=_row_ids_sha256(rows),
        schema_version=SCHEMA_VERSION,
    )
    return csv_bytes, manifest
