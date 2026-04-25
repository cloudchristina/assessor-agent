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
