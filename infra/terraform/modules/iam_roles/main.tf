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
    "adversarial_probe",
    "reviewer_disagreement_digest",
    "shadow_eval",
    "canary_orchestrator",
    "drift_detector",
    "reviewer_disagreement",
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

# ---------------- adversarial-probe ----------------
data "aws_iam_policy_document" "adversarial_probe" {
  statement {
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.runs_bucket_arn}/narratives/*", "${var.runs_bucket_arn}/rules/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_findings_arn]
  }
}

resource "aws_iam_role_policy" "adversarial_probe" {
  name   = "adversarial-probe"
  role   = aws_iam_role.lambda["adversarial_probe"].id
  policy = data.aws_iam_policy_document.adversarial_probe.json
}

# ---------------- reviewer-disagreement-digest ----------------
data "aws_iam_policy_document" "reviewer_disagreement_digest" {
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:Scan"]
    resources = ["arn:aws:dynamodb:*:*:table/${var.name_prefix}-golden-set-candidates"]
  }
  statement {
    effect    = "Allow"
    actions   = ["ses:SendEmail"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "reviewer_disagreement_digest" {
  name   = "reviewer-disagreement-digest"
  role   = aws_iam_role.lambda["reviewer_disagreement_digest"].id
  policy = data.aws_iam_policy_document.reviewer_disagreement_digest.json
}

# ---------------- shadow-eval ----------------
# Triggered by DDB Streams (runs INSERT). Invokes judge Lambda for Bedrock
# scoring, writes shadow_score back to runs, writes drift signal to
# drift_signals table.
data "aws_iam_policy_document" "shadow_eval" {
  statement {
    effect    = "Allow"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = ["*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:GetItem"]
    resources = [var.runs_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${var.runs_bucket_arn}/narratives/*", "${var.runs_bucket_arn}/rules/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:UpdateItem"]
    resources = [var.runs_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:PutItem"]
    resources = [var.drift_signals_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = ["arn:aws:lambda:*:*:function:*-judge"]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_findings_arn]
  }
  # DDB Streams access (for event source mapping)
  statement {
    effect = "Allow"
    actions = [
      "dynamodb:GetRecords",
      "dynamodb:GetShardIterator",
      "dynamodb:DescribeStream",
      "dynamodb:ListStreams",
    ]
    resources = ["${var.runs_table_arn}/stream/*"]
  }
}

resource "aws_iam_role_policy" "shadow_eval" {
  name   = "shadow-eval"
  role   = aws_iam_role.lambda["shadow_eval"].id
  policy = data.aws_iam_policy_document.shadow_eval.json
}

# ---------------- canary-orchestrator ----------------
# Triggered by EventBridge weekly cron. Starts a Step Functions execution
# with a synthetic fixture, waits, then writes canary results to DDB.
data "aws_iam_policy_document" "canary_orchestrator" {
  statement {
    effect    = "Allow"
    actions   = ["states:StartExecution"]
    resources = ["arn:aws:states:*:*:stateMachine:${var.name_prefix}-*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["states:DescribeExecution"]
    # DescribeExecution operates on execution ARNs, distinct from stateMachine ARNs.
    resources = ["arn:aws:states:*:*:execution:${var.name_prefix}-*:*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:PutItem"]
    resources = [var.canary_results_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:GetItem"]
    resources = [var.runs_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${var.runs_bucket_arn}/fixtures/*", "${var.runs_bucket_arn}/canary/*"]
  }
  statement {
    effect  = "Allow"
    actions = ["kms:Encrypt", "kms:Decrypt", "kms:GenerateDataKey"]
    # Needs both raw (S3 fixture upload + read) and findings (runs DDB table SSE).
    resources = [var.kms_raw_arn, var.kms_findings_arn]
  }
}

resource "aws_iam_role_policy" "canary_orchestrator" {
  name   = "canary-orchestrator"
  role   = aws_iam_role.lambda["canary_orchestrator"].id
  policy = data.aws_iam_policy_document.canary_orchestrator.json
}

# ---------------- drift-detector ----------------
# Triggered by EventBridge weekly cron. Scans runs table, writes drift
# signals and drift baseline.
data "aws_iam_policy_document" "drift_detector" {
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:Query", "dynamodb:Scan"]
    resources = [var.runs_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:PutItem"]
    resources = [var.drift_signals_table_arn, var.drift_baseline_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_findings_arn]
  }
}

resource "aws_iam_role_policy" "drift_detector" {
  name   = "drift-detector"
  role   = aws_iam_role.lambda["drift_detector"].id
  policy = data.aws_iam_policy_document.drift_detector.json
}

# ---------------- reviewer-disagreement ----------------
# Triggered by DDB Streams (findings MODIFY). Promotes high-disagreement
# findings to the golden-set-candidates table.
data "aws_iam_policy_document" "reviewer_disagreement" {
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:GetItem"]
    resources = [var.findings_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:PutItem"]
    resources = [var.golden_set_candidates_table_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [var.kms_findings_arn]
  }
  # DDB Streams access (for event source mapping)
  statement {
    effect = "Allow"
    actions = [
      "dynamodb:GetRecords",
      "dynamodb:GetShardIterator",
      "dynamodb:DescribeStream",
      "dynamodb:ListStreams",
    ]
    resources = ["${var.findings_table_arn}/stream/*"]
  }
}

resource "aws_iam_role_policy" "reviewer_disagreement" {
  name   = "reviewer-disagreement"
  role   = aws_iam_role.lambda["reviewer_disagreement"].id
  policy = data.aws_iam_policy_document.reviewer_disagreement.json
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
