resource "aws_dynamodb_table" "runs" {
  name         = "${var.name_prefix}-runs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_id"

  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

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

  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

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

# Plan 2 — eval suite tables (§2.4 and §5.x)

resource "aws_dynamodb_table" "eval_results" {
  name         = "${var.name_prefix}-eval-results"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "eval_run_id"
  range_key    = "case_id"

  attribute {
    name = "eval_run_id"
    type = "S"
  }

  attribute {
    name = "case_id"
    type = "S"
  }

  attribute {
    name = "branch"
    type = "S"
  }

  attribute {
    name = "created_at"
    type = "S"
  }

  global_secondary_index {
    name            = "branch_index"
    hash_key        = "branch"
    range_key       = "created_at"
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

resource "aws_dynamodb_table" "drift_baseline" {
  name         = "${var.name_prefix}-drift-baseline"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "metric_name"
  range_key    = "date"

  attribute {
    name = "metric_name"
    type = "S"
  }

  attribute {
    name = "date"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }
}

resource "aws_dynamodb_table" "golden_set_candidates" {
  name         = "${var.name_prefix}-golden-set-candidates"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "candidate_id"

  attribute {
    name = "candidate_id"
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

resource "aws_dynamodb_table" "canary_results" {
  name         = "${var.name_prefix}-canary-results"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "canary_run_id"

  attribute {
    name = "canary_run_id"
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

resource "aws_dynamodb_table" "drift_signals" {
  name         = "${var.name_prefix}-drift-signals"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "signal_id"

  attribute {
    name = "signal_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }
}
