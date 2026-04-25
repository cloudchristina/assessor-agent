"""Test-session env vars so moto can intercept boto3 clients that are
constructed at module-import time (before a per-test @mock_aws activates)."""
import os

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-southeast-2")
