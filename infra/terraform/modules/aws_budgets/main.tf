resource "aws_sns_topic" "budget" {
  name              = "${var.name_prefix}-budget"
  kms_master_key_id = "alias/aws/sns"
  tags              = var.tags
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.budget.arn
  protocol  = "email"
  endpoint  = var.email
}

locals {
  budgets = {
    early_warn   = 50
    steady_state = 150
    investigate  = 250
  }
}

resource "aws_budgets_budget" "monthly" {
  for_each     = local.budgets
  name         = "${var.name_prefix}-${each.key}"
  budget_type  = "COST"
  limit_amount = each.value
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget.arn]
  }
}
