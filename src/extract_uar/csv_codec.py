"""Lossless CSV cell encoding for UARRow fields with list/dict/bool/None types."""
from __future__ import annotations
from datetime import datetime

_LIST_FIELDS = {"server_roles", "db_roles"}
_DICT_FIELDS = {"grant_counts", "deny_counts"}
_BOOL_FIELDS = {"explicit_read", "explicit_write", "explicit_exec", "explicit_admin"}
_NULLABLE_STR = {"mapped_user_name", "user_type", "default_schema"}
_NULLABLE_DATETIME = {"last_active_date"}


def encode_row(row: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in row.items():
        if k in _LIST_FIELDS:
            out[k] = ", ".join(sorted(v or []))
        elif k in _DICT_FIELDS:
            out[k] = "; ".join(f"{a}={b}" for a, b in sorted((v or {}).items()))
        elif k in _BOOL_FIELDS:
            out[k] = "True" if v else "False"
        elif v is None:
            out[k] = ""
        elif isinstance(v, datetime):
            out[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        else:
            out[k] = str(v)
    return out


def decode_row(row: dict[str, str]) -> dict:
    out: dict = {}
    for k, v in row.items():
        if k in _LIST_FIELDS:
            out[k] = [s.strip() for s in v.split(",") if s.strip()]
        elif k in _DICT_FIELDS:
            d: dict[str, int] = {}
            for pair in v.split(";"):
                pair = pair.strip()
                if not pair:
                    continue
                key, _, val = pair.partition("=")
                d[key.strip()] = int(val.strip())
            out[k] = d
        elif k in _BOOL_FIELDS:
            out[k] = v == "True"
        elif k in _NULLABLE_STR:
            out[k] = None if v == "" else v
        elif k in _NULLABLE_DATETIME:
            out[k] = None if v == "" else datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
        elif k == "login_create_date":
            out[k] = datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
        else:
            out[k] = v
    return out
