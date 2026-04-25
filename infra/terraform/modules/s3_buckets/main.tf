resource "aws_s3_bucket" "runs" {
  bucket = "${var.name_prefix}-runs"
}

resource "aws_s3_bucket_versioning" "runs" {
  bucket = aws_s3_bucket.runs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "runs" {
  bucket = aws_s3_bucket.runs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.raw_kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "runs" {
  bucket                  = aws_s3_bucket.runs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "runs" {
  bucket = aws_s3_bucket.runs.id
  rule {
    id     = "expire-validated"
    status = "Enabled"
    filter {
      prefix = "validated/"
    }
    expiration {
      days = var.validated_expiration_days
    }
  }
}

# Reports bucket: Object Lock requires versioning and must be enabled at create
resource "aws_s3_bucket" "reports" {
  bucket              = "${var.name_prefix}-reports"
  object_lock_enabled = true
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_object_lock_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    default_retention {
      mode  = "GOVERNANCE"
      years = var.object_lock_years
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.reports_kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
