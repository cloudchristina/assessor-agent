"""Refactored extractor Lambda.

Fixes the draft's known bugs (spec section 2.2 C1): SERVER_CONFIGS is
now loaded lazily inside the handler, per-server/per-DB failures are
collected and re-raised instead of silently skipped, TLS is enforced at
the connection layer, and output is a deterministic CSV plus a SHA-256
manifest under `raw/dt=YYYY-MM-DD/cadence={weekly|monthly}/`.
"""
from __future__ import annotations
import csv
import io
import json
import os
from collections import defaultdict
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import boto3

from src.shared.logging import get_logger
from src.extract_uar.access_logic import (
    derive_access_level,
    fmt_dt,
    sid_hex,
    summarize_permissions,
)
from src.extract_uar.connection import get_connection
from src.extract_uar.csv_codec import decode_row
from src.extract_uar.csv_writer import build_csv_and_manifest
from src.extract_uar.sql_queries import (
    DB_PERMISSIONS_SQL,
    DB_ROLE_MEMBERS_SQL,
    DB_USERS_SQL,
    LAST_ACTIVE_SQL,
    SERVER_LOGINS_SQL,
    SERVER_ROLE_MEMBERS_SQL,
)


log = get_logger("extract-uar")
SYDNEY = ZoneInfo("Australia/Sydney")


def _s3():
    return boto3.client("s3")


def _secrets():
    return boto3.client("secretsmanager")


def _run_id(cadence: str, started_at: datetime) -> str:
    return f"run_{started_at.strftime('%Y-%m-%d')}_{cadence}"


def _object_prefix(started_at: datetime, cadence: str) -> str:
    return f"raw/dt={started_at.strftime('%Y-%m-%d')}/cadence={cadence}"


def get_server_configs() -> list[dict]:
    """Load server configurations from Secrets Manager. Raises if none found
    or SECRETS_MANAGER_ARNS is missing / malformed."""
    raw = os.environ.get("SECRETS_MANAGER_ARNS")
    if not raw:
        raise RuntimeError("SECRETS_MANAGER_ARNS not set")
    arns = json.loads(raw)
    if not arns:
        raise RuntimeError("SECRETS_MANAGER_ARNS is empty")

    sm = _secrets()
    configs: list[dict] = []
    for arn in arns:
        resp = sm.get_secret_value(SecretId=arn)
        creds = json.loads(resp["SecretString"])
        databases = [
            db.strip()
            for db in creds.get("databases", "").split(",")
            if db.strip()
        ]
        configs.append({
            "server": creds["host"],
            "port": int(creds.get("port", 1433)),
            "databases": databases,
            "username": creds["username"],
            "password": creds["password"],
        })
    return configs


def _read_synthetic_rows(uri: str) -> list[dict]:
    p = urlparse(uri)
    body = _s3().get_object(Bucket=p.netloc, Key=p.path.lstrip("/"))["Body"].read()
    reader = csv.DictReader(io.StringIO(body.decode("utf-8")))
    return [decode_row(r) for r in reader]


def _rows_from_live_servers(
    configs: list[dict],
    *,
    correlation_id: str,
) -> tuple[list[dict], list[str], list[str]]:
    """Query each server/database. Collects failures; raises at the end if any."""
    failures: list[dict] = []
    rows: list[dict] = []
    servers_processed: list[str] = []
    databases_processed: list[str] = []

    for cfg in configs:
        server = cfg["server"]
        servers_processed.append(server)
        log.info("extract.server.start", extra={"correlation_id": correlation_id, "server": server})
        try:
            server_conn = get_connection(
                server=server,
                port=cfg["port"],
                username=cfg["username"],
                password=cfg["password"],
                database=None,
            )
        except Exception as e:
            failures.append({"scope": "server", "server": server, "error": str(e)})
            continue

        try:
            server_cur = server_conn.cursor()
            server_cur.execute(SERVER_LOGINS_SQL)
            logins = list(server_cur)
            server_cur.execute(SERVER_ROLE_MEMBERS_SQL)
            role_rows = list(server_cur)
            server_cur.execute(LAST_ACTIVE_SQL)
            last_active_rows = list(server_cur)

            server_roles_map: dict[str, list[str]] = defaultdict(list)
            for rr in role_rows:
                server_roles_map[rr["LoginName"]].append(rr["ServerRoleName"])
            last_active_map: dict[str, datetime] = {
                la["login_name"]: la["LastActiveDate"] for la in last_active_rows
            }
            login_meta_map = {lg["LoginName"]: lg for lg in logins}

            for db in cfg["databases"]:
                databases_processed.append(db)
                log.info(
                    "extract.db.start",
                    extra={"correlation_id": correlation_id, "server": server, "database": db},
                )
                try:
                    db_conn = get_connection(
                        server=server,
                        port=cfg["port"],
                        username=cfg["username"],
                        password=cfg["password"],
                        database=db,
                    )
                except Exception as e:
                    failures.append({"scope": "database", "server": server, "database": db, "error": str(e)})
                    continue

                try:
                    db_cur = db_conn.cursor()
                    db_cur.execute(DB_USERS_SQL)
                    db_users = list(db_cur)
                    db_cur.execute(DB_ROLE_MEMBERS_SQL)
                    db_role_rows = list(db_cur)
                    db_cur.execute(DB_PERMISSIONS_SQL)
                    db_perm_rows = list(db_cur)

                    user_sid_map = {sid_hex(u.get("UserSid")) or "": u for u in db_users}
                    db_roles_map: dict[str, list[str]] = defaultdict(list)
                    for rr in db_role_rows:
                        db_roles_map[rr["UserName"]].append(rr["RoleName"])
                    db_perms_map: dict[str, list[dict]] = defaultdict(list)
                    for pr in db_perm_rows:
                        db_perms_map[pr["UserName"]].append(pr)

                    for login_name, meta in login_meta_map.items():
                        login_sid = sid_hex(meta.get("LoginSid")) or ""
                        mapped = user_sid_map.get(login_sid)
                        mapped_name = mapped["UserName"] if mapped else None
                        db_roles = db_roles_map.get(mapped_name or "", []) if mapped_name else []
                        perms = db_perms_map.get(mapped_name or "", []) if mapped_name else []
                        perm_summary = summarize_permissions(perms) if mapped_name else summarize_permissions([])
                        access = derive_access_level(server_roles_map.get(login_name, []), db_roles, perm_summary)

                        grant_counts: dict[str, int] = {}
                        deny_counts: dict[str, int] = {}
                        for k, c in perm_summary["perm_counter"].items():
                            state, perm = k.split(":", 1)
                            if state == "GRANT":
                                grant_counts[perm] = grant_counts.get(perm, 0) + c
                            elif state == "DENY":
                                deny_counts[perm] = deny_counts.get(perm, 0) + c

                        rows.append({
                            "login_name": login_name,
                            "login_type": meta.get("LoginType"),
                            "login_create_date": meta.get("LoginCreateDate"),
                            "last_active_date": last_active_map.get(login_name),
                            "server_roles": server_roles_map.get(login_name, []),
                            "database": f"{db} ({server})",
                            "mapped_user_name": mapped_name,
                            "user_type": mapped["UserType"] if mapped else None,
                            "default_schema": mapped["DefaultSchema"] if mapped else None,
                            "db_roles": db_roles,
                            "explicit_read": perm_summary["explicit_read"],
                            "explicit_write": perm_summary["explicit_write"],
                            "explicit_exec": perm_summary["explicit_exec"],
                            "explicit_admin": perm_summary["explicit_admin"],
                            "access_level": access,
                            "grant_counts": grant_counts,
                            "deny_counts": deny_counts,
                        })
                except Exception as e:
                    failures.append({"scope": "database-query", "server": server, "database": db, "error": str(e)})
                finally:
                    try:
                        db_conn.close()
                    except Exception:
                        pass
        except Exception as e:
            failures.append({"scope": "server-query", "server": server, "error": str(e)})
        finally:
            try:
                server_conn.close()
            except Exception:
                pass

    if failures:
        log.error("extract.failures", extra={"correlation_id": correlation_id, "failures": failures})
        raise RuntimeError(f"extract-uar failures (no silent skip): {failures}")
    return rows, servers_processed, databases_processed


def _parse_started_at(raw: str | None) -> datetime:
    """Accept ISO-8601 with or without timezone; normalise to Sydney wall time."""
    if raw is None:
        return datetime.now(SYDNEY).replace(tzinfo=None)
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(SYDNEY).replace(tzinfo=None)


def lambda_handler(event: dict, _context: object) -> dict:
    cadence = event["cadence"]
    started_at = _parse_started_at(event.get("started_at"))
    run_id = _run_id(cadence, started_at)
    bucket = os.environ["RUNS_BUCKET"]
    log.info("extract.start", extra={"correlation_id": run_id, "cadence": cadence})

    synth_uri = os.environ.get("SYNTHETIC_DATA_S3_URI")
    if synth_uri:
        log.info("extract.synthetic", extra={"correlation_id": run_id, "uri": synth_uri})
        rows = _read_synthetic_rows(synth_uri)
        servers = sorted({r["database"].rpartition("(")[2].rstrip(")").strip() for r in rows})
        databases = sorted({r["database"] for r in rows})
    else:
        configs = get_server_configs()
        rows, servers, databases = _rows_from_live_servers(configs, correlation_id=run_id)

    csv_bytes, manifest = build_csv_and_manifest(
        rows,
        run_id=run_id,
        servers=servers,
        databases=databases,
        cadence=cadence,
        extracted_at=started_at,
    )

    prefix = _object_prefix(started_at, cadence)
    csv_key = f"{prefix}/uar.csv"
    manifest_key = f"{prefix}/manifest.json"

    s3 = _s3()
    s3.put_object(
        Bucket=bucket,
        Key=csv_key,
        Body=csv_bytes,
        ContentType="text/csv",
        ServerSideEncryption="aws:kms",
    )
    s3.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=manifest.model_dump_json().encode("utf-8"),
        ContentType="application/json",
        ServerSideEncryption="aws:kms",
    )

    # datetime encoding is handled by Pydantic's JSON mode — fmt_dt keeps
    # the legacy formatting helper in the module's API surface for callers
    # that want a pre-formatted log line.
    _ = fmt_dt

    log.info(
        "extract.done",
        extra={"correlation_id": run_id, "row_count": manifest.row_count},
    )
    return {
        "csv_s3_uri": f"s3://{bucket}/{csv_key}",
        "manifest_s3_uri": f"s3://{bucket}/{manifest_key}",
        "bucket": bucket,
        "run_id": run_id,
    }
