data "aws_iam_policy_document" "assume_lambda" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "assume_sfn" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

# Permissions boundary: deny every Lambda role the ability to change IAM or
# schedule KMS key deletion, regardless of any inline policy we attach.
data "aws_iam_policy_document" "boundary" {
  statement {
    sid       = "AllowEverythingElse"
    effect    = "Allow"
    actions   = ["*"]
    resources = ["*"]
  }
  statement {
    sid       = "DenyIamAndKmsScheduling"
    effect    = "Deny"
    actions   = ["iam:*", "kms:ScheduleKeyDeletion", "kms:Disable*"]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "boundary" {
  name   = "${var.name_prefix}-lambda-boundary"
  policy = data.aws_iam_policy_document.boundary.json
}

locals {
  lambda_names = [
    "extract_uar",
    "validate_and_hash",
    "rules_engine",
    "agent_narrator",
    "citation_gate",
    "reconciliation_gate",
    "entity_grounding_gate",
    "judge",
    "publish_triage",
    "generate_pdf",
  ]
}

# Every Lambda needs CloudWatch Logs + X-Ray.
data "aws_iam_policy_document" "base" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
    ]
    resources = ["*"]
  }
  # Lambda's CreateFunction validates that the role can SendMessage on its
  # configured DLQ. The DLQ name follows the pattern <name_prefix>-<fn>-dlq.
  statement {
    effect    = "Allow"
    actions   = ["sqs:SendMessage"]
    resources = ["arn:aws:sqs:*:*:${var.name_prefix}-*-dlq"]
  }
}

resource "aws_iam_role" "lambda" {
  for_each             = toset(local.lambda_names)
  name                 = "${var.name_prefix}-${replace(each.key, "_", "-")}"
  assume_role_policy   = data.aws_iam_policy_document.assume_lambda.json
  permissions_boundary = aws_iam_policy.boundary.arn
}

resource "aws_iam_role_policy" "base" {
  for_each = aws_iam_role.lambda
  name     = "base"
  role     = each.value.id
  policy   = data.aws_iam_policy_document.base.json
}

# ---------------- extract-uar ----------------
data "aws_iam_policy_document" "extract_uar" {
  statement {
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = length(var.secret_arns) > 0 ? var.secret_arns : ["*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:PutObjectAcl"]
    resources = ["${var.runs_bucket_arn}/raw/*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "s3:GetObject",
    ]
    resources = ["${var.runs_bucket_arn}/fixtures/*"]
  }
  statement {
    effect = "Allow"
    # Decrypt for reading the synthetic-data fixture object back from S3.
    actions   = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
    resources = [var.kms_raw_arn]
  }
}

resource "aws_iam_role_policy" "extract_uar" {
  name   = "extract-uar"
  role   = aws_iam_role.lambda["extract_uar"].id
  policy = data.aws_iam_policy_document.extract_uar.json
}

# ---------------- validate-and-hash ----------------
data "aws_iam_policy_document" "validate_and_hash" {
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.runs_bucket_arn}/raw/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${var.runs_bucket_arn}/validated/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [var.kms_raw_arn, var.kms_findings_arn]
  }
}

resource "aws_iam_role_policy" "validate_and_hash" {
  name   = "validate-and-hash"
  role   = aws_iam_role.lambda["validate_and_hash"].id
  policy = data.aws_iam_policy_document.validate_and_hash.json
}

# ---------------- rules-engine ----------------
data "aws_iam_policy_document" "rules_engine" {
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.runs_bucket_arn}/validated/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${var.runs_bucket_arn}/rules/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [var.kms_findings_arn]
  }
}

resource "aws_iam_role_policy" "rules_engine" {
  name   = "rules-engine"
  role   = aws_iam_role.lambda["rules_engine"].id
  policy = data.aws_iam_policy_document.rules_engine.json
}

# ---------------- agent-narrator ----------------
data "aws_iam_policy_document" "agent_narrator" {
  statement {
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["*"]
  }
  dynamic "statement" {
    for_each = var.guardrail_arn == "" ? [] : [1]
    content {
      effect    = "Allow"
      actions   = ["bedrock:ApplyGuardrail"]
      resources = [var.guardrail_arn]
    }
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.runs_bucket_arn}/rules/*", "${var.runs_bucket_arn}/prior/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${var.runs_bucket_arn}/narratives/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:GetItem"]
    resources = [var.findings_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [var.kms_findings_arn]
  }
}

resource "aws_iam_role_policy" "agent_narrator" {
  name   = "agent-narrator"
  role   = aws_iam_role.lambda["agent_narrator"].id
  policy = data.aws_iam_policy_document.agent_narrator.json
}

# ---------------- gates (citation / reconciliation / entity_grounding) ----------------
data "aws_iam_policy_document" "gate_common" {
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.runs_bucket_arn}/rules/*", "${var.runs_bucket_arn}/narratives/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_findings_arn]
  }
}

resource "aws_iam_role_policy" "citation_gate" {
  name   = "citation-gate"
  role   = aws_iam_role.lambda["citation_gate"].id
  policy = data.aws_iam_policy_document.gate_common.json
}

resource "aws_iam_role_policy" "reconciliation_gate" {
  name   = "reconciliation-gate"
  role   = aws_iam_role.lambda["reconciliation_gate"].id
  policy = data.aws_iam_policy_document.gate_common.json
}

resource "aws_iam_role_policy" "entity_grounding_gate" {
  name   = "entity-grounding-gate"
  role   = aws_iam_role.lambda["entity_grounding_gate"].id
  policy = data.aws_iam_policy_document.gate_common.json
}

# ---------------- judge ----------------
data "aws_iam_policy_document" "judge" {
  statement {
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.runs_bucket_arn}/rules/*", "${var.runs_bucket_arn}/narratives/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_findings_arn]
  }
}

resource "aws_iam_role_policy" "judge" {
  name   = "judge"
  role   = aws_iam_role.lambda["judge"].id
  policy = data.aws_iam_policy_document.judge.json
}

# ---------------- publish-triage ----------------
data "aws_iam_policy_document" "publish_triage" {
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.runs_bucket_arn}/rules/*", "${var.runs_bucket_arn}/narratives/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:PutItem", "dynamodb:BatchWriteItem", "dynamodb:UpdateItem"]
    resources = [var.runs_table_arn, var.findings_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [var.kms_findings_arn]
  }
}

resource "aws_iam_role_policy" "publish_triage" {
  name   = "publish-triage"
  role   = aws_iam_role.lambda["publish_triage"].id
  policy = data.aws_iam_policy_document.publish_triage.json
}

# ---------------- generate-pdf ----------------
data "aws_iam_policy_document" "generate_pdf" {
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.runs_bucket_arn}/rules/*", "${var.runs_bucket_arn}/narratives/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:GetItem"]
    resources = [var.runs_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject"]
    resources = ["${var.reports_bucket_arn}/reports/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [var.kms_findings_arn, var.kms_reports_arn]
  }
}

resource "aws_iam_role_policy" "generate_pdf" {
  name   = "generate-pdf"
  role   = aws_iam_role.lambda["generate_pdf"].id
  policy = data.aws_iam_policy_document.generate_pdf.json
}

# ---------------- step-functions ----------------
resource "aws_iam_role" "step_functions" {
  name                 = "${var.name_prefix}-sfn"
  assume_role_policy   = data.aws_iam_policy_document.assume_sfn.json
  permissions_boundary = aws_iam_policy.boundary.arn
}

data "aws_iam_policy_document" "step_functions" {
  statement {
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = ["*"]
  }
  statement {
    effect = "Allow"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "logs:CreateLogDelivery",
      "logs:GetLogDelivery",
      "logs:UpdateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:DescribeResourcePolicies",
      "logs:DescribeLogGroups",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "step_functions" {
  name   = "step-functions"
  role   = aws_iam_role.step_functions.id
  policy = data.aws_iam_policy_document.step_functions.json
}
