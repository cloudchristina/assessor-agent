data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "scheduler_invoke" {
  statement {
    effect    = "Allow"
    actions   = ["states:StartExecution"]
    resources = [var.state_machine_arn]
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.name_prefix}-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

resource "aws_iam_role_policy" "scheduler" {
  name   = "invoke-sfn"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler_invoke.json
}

resource "aws_scheduler_schedule" "weekly" {
  name                         = "${var.name_prefix}-weekly"
  schedule_expression          = var.weekly_cron
  schedule_expression_timezone = "Australia/Sydney"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.state_machine_arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      cadence    = "weekly"
      started_at = "<aws.scheduler.scheduled-time>"
    })
  }
}

resource "aws_scheduler_schedule" "monthly" {
  name                         = "${var.name_prefix}-monthly"
  schedule_expression          = var.monthly_cron
  schedule_expression_timezone = "Australia/Sydney"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.state_machine_arn
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      cadence    = "monthly"
      started_at = "<aws.scheduler.scheduled-time>"
    })
  }
}

# ---------------------------------------------------------------------------
# Reviewer-disagreement digest — Sunday 04:00 AEST (18:00 UTC Saturday)
# Runs after the canary + drift-detector have completed.
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "scheduler_digest_invoke" {
  statement {
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [var.reviewer_disagreement_digest_arn]
  }
}

resource "aws_iam_role" "scheduler_digest" {
  name               = "${var.name_prefix}-scheduler-digest"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

resource "aws_iam_role_policy" "scheduler_digest" {
  name   = "invoke-digest-lambda"
  role   = aws_iam_role.scheduler_digest.id
  policy = data.aws_iam_policy_document.scheduler_digest_invoke.json
}

resource "aws_scheduler_schedule" "reviewer_digest" {
  name                = "${var.name_prefix}-reviewer-digest"
  schedule_expression = "cron(0 18 ? * SUN *)" # 04:00 AEST = 18:00 UTC Saturday

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.reviewer_disagreement_digest_arn
    role_arn = aws_iam_role.scheduler_digest.arn
  }
}

# ---------------------------------------------------------------------------
# Canary orchestrator — Sunday 03:00 AEST (17:00 UTC Saturday)
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "scheduler_canary_invoke" {
  statement {
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [var.canary_orchestrator_arn]
  }
}

resource "aws_iam_role" "scheduler_canary" {
  name               = "${var.name_prefix}-scheduler-canary"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

resource "aws_iam_role_policy" "scheduler_canary" {
  name   = "invoke-canary-lambda"
  role   = aws_iam_role.scheduler_canary.id
  policy = data.aws_iam_policy_document.scheduler_canary_invoke.json
}

resource "aws_scheduler_schedule" "canary" {
  name                = "${var.name_prefix}-canary"
  schedule_expression = "cron(0 17 ? * SUN *)" # 03:00 AEST = 17:00 UTC Saturday

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.canary_orchestrator_arn
    role_arn = aws_iam_role.scheduler_canary.arn
  }
}

# ---------------------------------------------------------------------------
# Drift detector — Sunday 03:30 AEST (17:30 UTC Saturday)
# ---------------------------------------------------------------------------

data "aws_iam_policy_document" "scheduler_drift_invoke" {
  statement {
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [var.drift_detector_arn]
  }
}

resource "aws_iam_role" "scheduler_drift" {
  name               = "${var.name_prefix}-scheduler-drift"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

resource "aws_iam_role_policy" "scheduler_drift" {
  name   = "invoke-drift-lambda"
  role   = aws_iam_role.scheduler_drift.id
  policy = data.aws_iam_policy_document.scheduler_drift_invoke.json
}

resource "aws_scheduler_schedule" "drift" {
  name                = "${var.name_prefix}-drift"
  schedule_expression = "cron(30 17 ? * SUN *)" # 03:30 AEST = 17:30 UTC Saturday

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = var.drift_detector_arn
    role_arn = aws_iam_role.scheduler_drift.arn
  }
}
