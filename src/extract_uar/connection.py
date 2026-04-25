"""TLS-enforcing pymssql connection factory with tenacity retry on transient errors."""
from __future__ import annotations
import os
import pymssql
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))


class TlsRequiredError(RuntimeError):
    """Raised when caller tries to bypass TLS."""


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
    retry=retry_if_exception_type(pymssql.OperationalError),
    reraise=True,
)
def get_connection(
    server: str,
    port: int,
    username: str,
    password: str,
    database: str | None = None,
    timeout: int = 15,
    *,
    encrypt: str = "strict",
    tds_version: str = "7.4",
):
    """Open a TLS-enforced pymssql connection. `encrypt='strict'` disables
    fallback to cleartext; callers that pass anything else raise explicitly so
    TLS can never be silently disabled."""
    if encrypt != "strict":
        raise TlsRequiredError(f"encrypt must be 'strict', got {encrypt!r}")
    return pymssql.connect(
        server=server,
        port=port,
        user=username,
        password=password,
        database=database,
        timeout=timeout,
        as_dict=True,
        tds_version=tds_version,
        encrypt=encrypt,
    )
