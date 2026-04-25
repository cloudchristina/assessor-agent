"""C2 — parse CSV, Pydantic-validate every row, recompute hash, compare to manifest."""
from __future__ import annotations
import csv
import hashlib
import io
import json
from urllib.parse import urlparse
import boto3
from pydantic import TypeAdapter
from src.shared.logging import get_logger
from src.shared.models import UARRow, ExtractManifest
from src.extract_uar.csv_codec import decode_row

log = get_logger("validate-and-hash")
s3 = boto3.client("s3")
_rows_adapter = TypeAdapter(list[UARRow])


def _row_id_hash(rows: list[dict]) -> str:
    keys = sorted(f"{r['login_name']}||{r['database']}" for r in rows)
    return hashlib.sha256("\n".join(keys).encode()).hexdigest()


def lambda_handler(event: dict, _ctx: object) -> dict:
    csv_uri = urlparse(event["csv_s3_uri"])
    mfst_uri = urlparse(event["manifest_s3_uri"])
    csv_obj = s3.get_object(Bucket=csv_uri.netloc, Key=csv_uri.path.lstrip("/"))
    csv_text = csv_obj["Body"].read().decode("utf-8")
    raw_rows = list(csv.DictReader(io.StringIO(csv_text)))
    manifest = ExtractManifest.model_validate_json(
        s3.get_object(Bucket=mfst_uri.netloc, Key=mfst_uri.path.lstrip("/"))["Body"].read()
    )
    if _row_id_hash(raw_rows) != manifest.row_ids_sha256:
        raise RuntimeError("manifest_hash_mismatch")
    decoded = [decode_row(r) for r in raw_rows]
    validated = _rows_adapter.validate_python(decoded)
    out_key = f"validated/{manifest.run_id}.json"
    s3.put_object(
        Bucket=event["bucket"],
        Key=out_key,
        Body=json.dumps({
            "run_id": manifest.run_id,
            "rows": [r.model_dump(mode="json") for r in validated],
        }).encode(),
        ServerSideEncryption="aws:kms",
    )
    log.info("validate.done", extra={"correlation_id": manifest.run_id, "rows": len(validated)})
    return {
        "run_id": manifest.run_id,
        "rows_s3_uri": f"s3://{event['bucket']}/{out_key}",
        "manifest": manifest.model_dump(mode="json"),
        "bucket": event["bucket"],
        "cadence": manifest.cadence,
        "started_at": event.get("started_at"),
    }
