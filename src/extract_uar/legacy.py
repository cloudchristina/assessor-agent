"""Legacy extractor draft — kept for reference only during Plan 1 refactor.

This module is the user's original extractor implementation, preserved
verbatim so the refactored components in `access_logic.py`, `connection.py`,
`sql_queries.py`, `csv_codec.py`, `csv_writer.py`, and `handler.py` can be
diffed against the original. Known bugs (documented in spec section 2.2 C1):
module-level SERVER_CONFIGS call, silent `except: continue`, no manifest /
hash, no TLS enforcement, unstructured f-string logs, MAX_RETRIES unused.

Not imported by any production code path; do NOT add new logic here.
"""
import os
import json
import csv
import io
import time
import datetime
import boto3
import logging
import pymssql
from collections import defaultdict, Counter
from typing import Any, Dict, List, Optional
from botocore.exceptions import ClientError
from zoneinfo import ZoneInfo

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------- Config from Secrets Manager ----------
# We'll retrieve server configurations from Secrets Manager
# Build server configurations dynamically
SERVER_CONFIGS = []

# Get all server configs from Secrets Manager
def get_server_configs():
    """Get server configurations from AWS Secrets Manager."""
    logger.info("Retrieving server configurations from AWS Secrets Manager")
    secret_arns = json.loads(os.environ["SECRETS_MANAGER_ARNS"])


    secrets_client = boto3.client('secretsmanager')
    server_configs = []

    try:
        for secret_arn in secret_arns:
            logger.info(f"Get server config from AWS")
            secret_resp = secrets_client.get_secret_value(SecretId=secret_arn)
            creds = json.loads(secret_resp["SecretString"])

            # Extract databases from the credentials or use default
            databases = creds.get("databases", "").split(",") if "databases" in creds else []

            server_configs.append({
                            "server": creds["host"],
                            "port": int(creds.get("port", 1433)),
                            "databases": [db.strip() for db in databases if db.strip()],
                            "username": creds["username"],
                            "password": creds["password"]
                        })
            logger.info(f"Retrieved {creds['host']} DB configuration with {len(databases)} database(s)")
    except Exception as e:
        logger.error(f"Failed to retrieve DB configuration: {e}")

    if not server_configs:
        raise ValueError("No server configurations found in Secrets Manager")

    logger.info(f"Found {len(server_configs)} server configuration(s) to process")
    return server_configs

# Get server configurations from Secrets Manager
# (Original bug: this call happens at module import, long before any event.)
# Left as-is so the spec's C1 "Fixes required" list can be diffed.
# SERVER_CONFIGS = get_server_configs()

# Other configuration
ENVIRONMENT = os.environ.get("ENVIRONMENT")
BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
# Historical default — retained verbatim; refactored handler computes keys differently.
OBJECT_KEY = os.environ.get(
    "S3_OBJECT_KEY",
    f"uar-input-files/{(ENVIRONMENT or '').replace('cde', '')}/databases/database_users.csv",
)

DATE_STAMPED = os.environ.get("DATE_STAMPED", "true").lower() == "true"
TIMEZONE_SYDNEY = os.environ.get("TIMEZONE_SYDNEY", "true").lower() == "true"
TIMEOUT_SECS = int(os.environ.get("TIMEOUT_SECS", "30"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

# AWS clients
s3c = boto3.client("s3")
ssm = boto3.client("ssm")

# ----------------------------
# SQL (server scope)
# ----------------------------

# Only SQL logins, exclude disabled, include SID & dates
SERVER_LOGINS_SQL = """
SELECT
  sp.principal_id    AS PrincipalId,
  sp.name            AS LoginName,
  sp.type_desc       AS LoginType,
  sp.is_disabled     AS IsDisabled,
  sp.create_date     AS LoginCreateDate,
  sp.modify_date     AS ModifyDate,
  sp.sid             AS LoginSid
FROM sys.server_principals AS sp
WHERE sp.type = 'S'       -- SQL login only (exclude WINDOWS_LOGIN/ WINDOWS_GROUP)
  AND sp.is_disabled = 0  -- exclude disabled logins
  AND sp.sid IS NOT NULL
ORDER BY sp.name;
"""

SERVER_ROLE_MEMBERS_SQL = """
SELECT
  m.name AS LoginName,
  r.name AS ServerRoleName
FROM sys.server_role_members AS srm
JOIN sys.server_principals AS r ON r.principal_id = srm.role_principal_id  -- role
JOIN sys.server_principals AS m ON m.principal_id = srm.member_principal_id -- login
WHERE m.type = 'S'  -- SQL login only
ORDER BY m.name, r.name;
"""

# Best-effort "last active": current/most recent session on the instance
LAST_ACTIVE_SQL = """
SELECT login_name, MAX(login_time) AS LastActiveDate
FROM sys.dm_exec_sessions
GROUP BY login_name;
"""

# ----------------------------
# SQL (database scope)
# ----------------------------

DB_USERS_SQL = """
SELECT
  dp.name                     AS UserName,
  dp.type_desc                AS UserType,
  dp.authentication_type_desc AS AuthType,
  dp.create_date              AS CreateDate,
  dp.modify_date              AS ModifyDate,
  dp.default_schema_name      AS DefaultSchema,
  dp.sid                      AS UserSid
FROM sys.database_principals AS dp
WHERE dp.type IN ('S','U','G')
  AND dp.sid IS NOT NULL
  AND dp.principal_id > 4     -- exclude dbo, guest, INFORMATION_SCHEMA, sys
ORDER BY dp.name;
"""

DB_ROLE_MEMBERS_SQL = """
SELECT
  dp.name  AS UserName,
  rol.name AS RoleName
FROM sys.database_role_members AS drm
JOIN sys.database_principals AS rol ON rol.principal_id = drm.role_principal_id
JOIN sys.database_principals AS dp  ON dp.principal_id  = drm.member_principal_id
ORDER BY dp.name, rol.name;
"""

DB_PERMISSIONS_SQL = """
SELECT
  dp.name               AS UserName,
  perm.permission_name  AS Permission,
  perm.state_desc       AS StateDesc,    -- GRANT/DENY/REVOKE
  perm.class_desc       AS ClassDesc,    -- OBJECT_OR_COLUMN, SCHEMA, DATABASE, etc.
  OBJECT_SCHEMA_NAME(perm.major_id) AS ObjectSchema,
  OBJECT_NAME(perm.major_id)        AS ObjectName
FROM sys.database_permissions AS perm
JOIN sys.database_principals  AS dp
  ON perm.grantee_principal_id = dp.principal_id
WHERE dp.sid IS NOT NULL
  AND dp.principal_id > 4
ORDER BY dp.name, perm.permission_name;
"""

# ----------------------------
# Helpers / access logic
# ----------------------------

READ_PERMS = {"SELECT"}
WRITE_PERMS = {"INSERT", "UPDATE", "DELETE", "MERGE"}
EXEC_PERMS = {"EXECUTE"}
ADMIN_PERMS = {"ALTER", "CONTROL", "TAKE OWNERSHIP"}

# CSV columns
CSV_COLS = [
    "LoginName",
    "LoginType",
    "LoginCreateDate",
    "LastActiveDate",
    "ServerRoles",
    "Database",
    "MappedUserName",
    "UserType",
    "DefaultSchema",
    "DBRoles",
    "ExplicitRead",
    "ExplicitWrite",
    "ExplicitExecute",
    "ExplicitAdmin",
    "AccessLevel",
    "GrantCounts",
    "DenyCounts",
]


def get_connection(
    server: str,
    port: int,
    username: str,
    password: str,
    database: Optional[str] = None,
    timeout: int = 15,
):
    """Create a connection to SQL Server using pymssql."""
    return pymssql.connect(
        server=server,
        port=port,
        user=username,
        password=password,
        database=database,
        timeout=timeout,
        as_dict=True,
        tds_version="7.3",  # bug per spec: should be >= 7.4 with TLS
    )


def run_query(conn, sql: str) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql)
        return list(cur)


def fmt_dt(val):
    if val is None or val == "N/A":
        return "N/A"
    try:
        return val.strftime("%Y-%m-%d %H:%M:%S")
    except AttributeError:
        return str(val)


def sid_hex(sid: Any) -> Optional[str]:
    return sid.hex() if isinstance(sid, (bytes, bytearray)) else None


def summarize_permissions(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    counter = Counter()
    grants, denies = set(), set()
    for r in rows:
        state = (r.get("StateDesc") or "").upper()
        perm = (r.get("Permission") or "").upper()
        if not state or not perm:
            continue
        counter[f"{state}:{perm}"] += 1
        if state == "GRANT":
            grants.add(perm)
        elif state == "DENY":
            denies.add(perm)
    return {
        "perm_counter": counter,
        "grants": grants,
        "denies": denies,
        "explicit_read": any(p in grants for p in READ_PERMS),
        "explicit_write": any(p in grants for p in WRITE_PERMS),
        "explicit_exec": any(p in grants for p in EXEC_PERMS),
        "explicit_admin": any(p in grants for p in ADMIN_PERMS),
    }


def derive_access_level(
    server_roles: List[str],
    db_roles: List[str],
    perm_summary: Dict[str, Any],
) -> str:
    if any(r.lower() == "sysadmin" for r in server_roles):
        return "Admin"
    role_set = {r.lower() for r in db_roles}
    if "db_owner" in role_set or perm_summary.get("explicit_admin"):
        return "Admin"
    if "db_datawriter" in role_set or perm_summary.get("explicit_write"):
        return "Write"
    if "db_datareader" in role_set or perm_summary.get("explicit_read"):
        return "ReadOnly"
    return "Unknown"


def _final_key(base_key: str, date_stamped: bool):
    if not date_stamped:
        return base_key
    sydney_tz = ZoneInfo("Australia/Sydney")
    today = datetime.datetime.now(sydney_tz).strftime("%Y%m%d")
    if base_key.lower().endswith(".csv"):
        stem = base_key[:-4]
        return f"{stem}_{today}.csv"
    return f"{base_key}_{today}"


def get_credentials_for_server(server_config):
    return server_config["username"], server_config["password"]


def publish_sns_message(topic_arn, subject_suffix, message):
    if not topic_arn:
        logger.info("SNS_TOPIC_ARN not provided. Skipping SNS notification.")
        return
    try:
        sns_client = boto3.client("sns")
        sns_client.publish(
            TopicArn=topic_arn,
            Subject=f"SailPointAuditReport-{ENVIRONMENT} {subject_suffix}",
            Message=message,
        )
        logger.info(f"SNS notification sent: {subject_suffix}")
    except Exception as e:
        logger.error(f"Failed to publish SNS message: {e}")


# ---------- Lambda handler ----------
def lambda_handler(event, context):  # noqa: C901 — legacy, refactored elsewhere
    start_time = time.time()
    logger.info("Starting SQL Server users export")

    if not BUCKET_NAME:
        raise ValueError("BUCKET_NAME environment variable is not set")

    if not SERVER_CONFIGS:
        raise ValueError("No server configurations found.")

    logger.info(f"Found {len(SERVER_CONFIGS)} server configurations to process")

    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(CSV_COLS)

    total_rows = 0
    all_databases_processed = []

    for server_config in SERVER_CONFIGS:
        server = server_config["server"]
        port = server_config["port"]
        databases = server_config["databases"]

        logger.info(f"Processing server: {server}")

        try:
            username, password = get_credentials_for_server(server_config)
            server_conn = get_connection(
                server, port, username, password,
                database=None, timeout=TIMEOUT_SECS,
            )

            logins = run_query(server_conn, SERVER_LOGINS_SQL)
            role_rows = run_query(server_conn, SERVER_ROLE_MEMBERS_SQL)
            last_active_rows = run_query(server_conn, LAST_ACTIVE_SQL)

            server_roles_map = defaultdict(list)
            for rr in role_rows:
                server_roles_map[rr["LoginName"]].append(rr["ServerRoleName"])

            last_active_map = {}
            for la in last_active_rows:
                last_active_map[la["login_name"]] = la["LastActiveDate"]

            login_sid_map = {}
            login_meta_map = {}
            for lg in logins:
                login_meta_map[lg["LoginName"]] = lg
                login_sid_map[lg["LoginName"]] = sid_hex(lg.get("LoginSid")) or ""

            for db in databases:
                if not db.strip():
                    continue

                logger.info(f"Processing database: {db} on server {server}")
                all_databases_processed.append(f"{server}:{db}")

                try:
                    db_conn = get_connection(
                        server, port, username, password,
                        database=db, timeout=TIMEOUT_SECS,
                    )

                    db_users = run_query(db_conn, DB_USERS_SQL)
                    db_roles_rows = run_query(db_conn, DB_ROLE_MEMBERS_SQL)
                    db_perms_rows = run_query(db_conn, DB_PERMISSIONS_SQL)

                    user_sid_map = {}
                    for ur in db_users:
                        hx = sid_hex(ur.get("UserSid")) or ""
                        user_sid_map[hx] = ur

                    db_roles_map = defaultdict(list)
                    for rr in db_roles_rows:
                        db_roles_map[rr["UserName"]].append(rr["RoleName"])

                    db_perms_map = defaultdict(list)
                    for pr in db_perms_rows:
                        db_perms_map[pr["UserName"]].append(pr)

                    for login_name, meta in login_meta_map.items():
                        login_type = meta.get("LoginType")
                        login_created = meta.get("LoginCreateDate")
                        last_active = last_active_map.get(login_name, "N/A")
                        server_roles = server_roles_map.get(login_name, [])
                        login_sid_hx = login_sid_map.get(login_name, "")

                        mapped_user = user_sid_map.get(login_sid_hx)
                        mapped_name = mapped_user["UserName"] if mapped_user else ""
                        mapped_type = mapped_user["UserType"] if mapped_user else ""
                        default_schema = mapped_user["DefaultSchema"] if mapped_user else ""

                        db_roles = db_roles_map.get(mapped_name, []) if mapped_name else []
                        perms = db_perms_map.get(mapped_name, []) if mapped_name else []
                        perm_summary = summarize_permissions(perms) if mapped_name else {
                            "perm_counter": Counter(),
                            "explicit_read": False,
                            "explicit_write": False,
                            "explicit_exec": False,
                            "explicit_admin": False,
                        }
                        access = derive_access_level(server_roles, db_roles, perm_summary)

                        grant_counts, deny_counts = {}, {}
                        for k, c in perm_summary["perm_counter"].items():
                            state, perm = k.split(":", 1)
                            if state == "GRANT":
                                grant_counts[perm] = grant_counts.get(perm, 0) + c
                            elif state == "DENY":
                                deny_counts[perm] = deny_counts.get(perm, 0) + c

                        db_with_server = f"{db} ({server})"

                        writer.writerow([
                            login_name,
                            login_type,
                            fmt_dt(login_created),
                            fmt_dt(last_active),
                            ", ".join(server_roles),
                            db_with_server,
                            mapped_name,
                            mapped_type,
                            default_schema,
                            ", ".join(db_roles),
                            str(perm_summary.get("explicit_read", False)),
                            str(perm_summary.get("explicit_write", False)),
                            str(perm_summary.get("explicit_exec", False)),
                            str(perm_summary.get("explicit_admin", False)),
                            access,
                            "; ".join(f"{p}={c}" for p, c in sorted(grant_counts.items())),
                            "; ".join(f"{p}={c}" for p, c in sorted(deny_counts.items())),
                        ])
                        total_rows += 1

                except Exception as e:
                    # bug per spec: silent continue swallows per-DB failures.
                    logger.error(f"Error processing database {db} on server {server}: {e}")
                    continue
                finally:
                    try:
                        if "db_conn" in locals():
                            db_conn.close()
                    except Exception:
                        pass

        except Exception as e:
            # bug per spec: silent continue swallows per-server failures.
            logger.error(f"Error processing server {server}: {e}")
            continue

        finally:
            try:
                if "server_conn" in locals():
                    server_conn.close()
            except Exception:
                pass

    if total_rows == 0:
        error_msg = "No data was processed from any server/database"
        logger.error(error_msg)
        publish_sns_message(SNS_TOPIC_ARN, "SQL Server User Report Failed", error_msg)
        raise ValueError(error_msg)

    key = _final_key(OBJECT_KEY, DATE_STAMPED)
    bucket_name = BUCKET_NAME
    logger.info(f"Uploading to bucket: {bucket_name}")
    s3_client = s3c
    s3_client.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=csv_buffer.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )

    duration = time.time() - start_time
    message = (
        f"SQL Server user report Lambda executed successfully in {round(duration, 2)} seconds.\n\n"
        f"User report: {key}\n"
        f"Total users: {total_rows}\n"
    )
    logger.info(f"Export complete. {total_rows} row(s) written to s3://{bucket_name}/{key}")
    publish_sns_message(SNS_TOPIC_ARN, "SQL Server User Report Success", message)
    return json.dumps(message)
