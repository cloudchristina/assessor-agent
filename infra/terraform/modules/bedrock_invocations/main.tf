data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  create_kms = var.kms_key_arn == ""
  kms_arn    = local.create_kms ? aws_kms_key.bedrock[0].arn : var.kms_key_arn
}

# ── Optional dedicated KMS key ──────────────────────────────────────────────

data "aws_iam_policy_document" "bedrock_key" {
  count = local.create_kms ? 1 : 0

  statement {
    sid     = "AccountRoot"
    effect  = "Allow"
    actions = ["kms:*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    resources = ["*"]
  }

  statement {
    sid    = "BedrockLogging"
    effect = "Allow"
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_kms_key" "bedrock" {
  count                   = local.create_kms ? 1 : 0
  description             = "${var.name_prefix}-bedrock-invocations CMK"
  enable_key_rotation     = true
  deletion_window_in_days = 7
  policy                  = data.aws_iam_policy_document.bedrock_key[0].json
  tags                    = var.tags
}

resource "aws_kms_alias" "bedrock" {
  count         = local.create_kms ? 1 : 0
  name          = "alias/${var.name_prefix}-bedrock-invocations"
  target_key_id = aws_kms_key.bedrock[0].key_id
}

# ── S3 bucket ───────────────────────────────────────────────────────────────

resource "aws_s3_bucket" "bedrock_invocations" {
  bucket = "${var.name_prefix}-bedrock-invocations"
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "bedrock_invocations" {
  bucket = aws_s3_bucket.bedrock_invocations.id
  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "bedrock_invocations" {
  bucket = aws_s3_bucket.bedrock_invocations.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = local.kms_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "bedrock_invocations" {
  bucket                  = aws_s3_bucket.bedrock_invocations.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "bedrock_invocations" {
  bucket = aws_s3_bucket.bedrock_invocations.id
  rule {
    id     = "expire-90d"
    status = "Enabled"
    filter {}
    expiration {
      days = 90
    }
  }
}

# Allow Bedrock service principal to write invocation logs
data "aws_iam_policy_document" "bedrock_invocations" {
  statement {
    sid    = "BedrockPutObject"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.bedrock_invocations.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_s3_bucket_policy" "bedrock_invocations" {
  bucket = aws_s3_bucket.bedrock_invocations.id
  policy = data.aws_iam_policy_document.bedrock_invocations.json
}
