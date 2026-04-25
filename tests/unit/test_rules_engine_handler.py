import json
import boto3
from moto import mock_aws
from src.rules_engine.handler import lambda_handler


@mock_aws
def test_handler_writes_findings_json():
    s3 = boto3.client("s3", region_name="ap-southeast-2")
    s3.create_bucket(
        Bucket="test-bucket-123",
        CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"},
    )
    rows_json = json.dumps({"run_id": "run_x", "rows": []})
    s3.put_object(Bucket="test-bucket-123", Key="validated/run_x.json", Body=rows_json)
    event = {
        "run_id": "run_x",
        "rows_s3_uri": "s3://test-bucket-123/validated/run_x.json",
        "bucket": "test-bucket-123",
    }
    result = lambda_handler(event, None)
    assert "findings_s3_uri" in result
    assert result["summary"]["R1"] == 0
