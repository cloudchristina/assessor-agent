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
