resource "aws_dynamodb_table" "runs" {
  name         = "${var.name_prefix}-runs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_id"

  attribute {
    name = "run_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }
}

# Plan 1 deviation: Finding.databases / Finding.ism_controls are stored as
# List of String (L), not String Set (SS). DDB does not allow empty SS and
# requires explicit set() coercion, but Pydantic emits list[str] from
# model_dump(). The L attribute round-trips cleanly and supports empty
# arrays. Documented in Plan 1 Task 9.3.
resource "aws_dynamodb_table" "findings" {
  name         = "${var.name_prefix}-findings"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_id"
  range_key    = "finding_id"

  attribute {
    name = "run_id"
    type = "S"
  }

  attribute {
    name = "finding_id"
    type = "S"
  }

  attribute {
    name = "severity"
    type = "S"
  }

  attribute {
    name = "detected_at"
    type = "S"
  }

  global_secondary_index {
    name            = "severity_index"
    hash_key        = "severity"
    range_key       = "detected_at"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }
}
