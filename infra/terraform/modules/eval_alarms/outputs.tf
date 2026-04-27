output "sns_topic_arn" {
  description = "ARN of the SNS topic that receives all eval alarm notifications."
  value       = aws_sns_topic.alarms.arn
}

output "alarm_names" {
  description = "List of CloudWatch alarm names created by this module."
  value = [
    aws_cloudwatch_metric_alarm.judge_degraded.alarm_name,
    aws_cloudwatch_metric_alarm.shadow_drift.alarm_name,
    aws_cloudwatch_metric_alarm.canary_regression.alarm_name,
  ]
}
