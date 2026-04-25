"""SQL Server queries used by the extractor. Two scopes: server-level and
per-database. Kept as module-level constants so Lambda cold-start cost is paid
once and queries are easy to diff."""
from __future__ import annotations


# ----------------------------
# Server scope
# ----------------------------

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
WHERE sp.type = 'S'       -- SQL login only (exclude WINDOWS_LOGIN / WINDOWS_GROUP)
  AND sp.is_disabled = 0
  AND sp.sid IS NOT NULL
ORDER BY sp.name;
"""

SERVER_ROLE_MEMBERS_SQL = """
SELECT
  m.name AS LoginName,
  r.name AS ServerRoleName
FROM sys.server_role_members AS srm
JOIN sys.server_principals AS r ON r.principal_id = srm.role_principal_id
JOIN sys.server_principals AS m ON m.principal_id = srm.member_principal_id
WHERE m.type = 'S'
ORDER BY m.name, r.name;
"""

# Best-effort "last active": currently-connected sessions. Per spec section
# 2.2 C1, production should switch to SQL Server Audit file reads; for the
# demo we accept synthetic last_active_date instead.
LAST_ACTIVE_SQL = """
SELECT login_name, MAX(login_time) AS LastActiveDate
FROM sys.dm_exec_sessions
GROUP BY login_name;
"""

# ----------------------------
# Database scope
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
  perm.state_desc       AS StateDesc,
  perm.class_desc       AS ClassDesc,
  OBJECT_SCHEMA_NAME(perm.major_id) AS ObjectSchema,
  OBJECT_NAME(perm.major_id)        AS ObjectName
FROM sys.database_permissions AS perm
JOIN sys.database_principals  AS dp
  ON perm.grantee_principal_id = dp.principal_id
WHERE dp.sid IS NOT NULL
  AND dp.principal_id > 4
ORDER BY dp.name, perm.permission_name;
"""
