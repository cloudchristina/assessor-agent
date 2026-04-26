# Eval alarms module — judge degradation, shadow drift, canary regression.
#
# All three alarms publish to one SNS topic with an email subscription.
# Metric filters extract signals from CloudWatch Logs; DynamoDB built-in
# metrics cover the shadow-drift alarm.

# ---------------------------------------------------------------------------
# SNS topic + email subscription
# ---------------------------------------------------------------------------

resource "aws_sns_topic" "alarms" {
  name              = "${var.name_prefix}-eval-alarms"
  kms_master_key_id = "alias/aws/sns"

  tags = var.tags
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.email
}

# ---------------------------------------------------------------------------
# Alarm 1 — Judge degradation
# Fires when passed_int = 0 appears in judge logs for 3 consecutive days.
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_metric_filter" "judge_failed" {
  name           = "${var.name_prefix}-judge-failed"
  log_group_name = var.judge_log_group_name
  pattern        = "{ $.passed_int = 0 }"

  metric_transformation {
    name          = "JudgeFailures"
    namespace     = "AssessorAgent/Eval"
    value         = "1"
    default_value = 0
  }
}

resource "aws_cloudwatch_metric_alarm" "judge_degraded" {
  alarm_name          = "${var.name_prefix}-judge-degraded"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 3
  metric_name         = "JudgeFailures"
  namespace           = "AssessorAgent/Eval"
  period              = 86400 # 1 day
  statistic           = "Sum"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  alarm_description   = "Judge has failed at least once per day for 3 consecutive days"

  tags = var.tags

  depends_on = [aws_cloudwatch_log_metric_filter.judge_failed]
}

# ---------------------------------------------------------------------------
# Alarm 2 — Shadow drift
# Fires when any PutItem lands in the drift_signals table in the last 24 h,
# indicating shadow eval detected a divergence.
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "shadow_drift" {
  alarm_name          = "${var.name_prefix}-shadow-drift"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "SuccessfulRequestCount"
  namespace           = "AWS/DynamoDB"

  dimensions = {
    TableName = var.drift_signals_table_name
    Operation = "PutItem"
  }

  period             = 86400 # 1 day
  statistic          = "Sum"
  threshold          = 0
  treat_missing_data = "notBreaching"
  alarm_actions      = [aws_sns_topic.alarms.arn]
  alarm_description  = "Shadow eval or drift detector wrote a drift signal in the last 24h"

  tags = var.tags
}

# ---------------------------------------------------------------------------
# Alarm 3 — Canary regression
# Fires when canary_orchestrator logs drift_detected = true in the last week.
# ---------------------------------------------------------------------------

resource "aws_cloudwatch_log_metric_filter" "canary_drift" {
  name           = "${var.name_prefix}-canary-drift"
  log_group_name = "/aws/lambda/${var.name_prefix}-canary-orchestrator"
  pattern        = "{ $.drift_detected = true }"

  metric_transformation {
    name          = "CanaryDriftCount"
    namespace     = "AssessorAgent/Eval"
    value         = "1"
    default_value = 0
  }
}

resource "aws_cloudwatch_metric_alarm" "canary_regression" {
  alarm_name          = "${var.name_prefix}-canary-regression"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "CanaryDriftCount"
  namespace           = "AssessorAgent/Eval"
  period              = 604800 # 1 week — matches canary schedule
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alarms.arn]
  alarm_description   = "Weekly canary detected drift vs baseline"

  tags = var.tags

  depends_on = [aws_cloudwatch_log_metric_filter.canary_drift]
}
