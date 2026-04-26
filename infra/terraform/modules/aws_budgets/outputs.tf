output "sns_topic_arn" {
  value       = aws_sns_topic.budget.arn
  description = "ARN of the SNS topic that receives budget alert notifications."
}
