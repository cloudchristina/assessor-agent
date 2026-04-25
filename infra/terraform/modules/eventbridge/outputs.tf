output "weekly_schedule_arn" {
  value = aws_scheduler_schedule.weekly.arn
}

output "monthly_schedule_arn" {
  value = aws_scheduler_schedule.monthly.arn
}
