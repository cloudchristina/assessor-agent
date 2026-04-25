output "runs_bucket_name" {
  value = aws_s3_bucket.runs.bucket
}

output "runs_bucket_arn" {
  value = aws_s3_bucket.runs.arn
}

output "reports_bucket_name" {
  value = aws_s3_bucket.reports.bucket
}

output "reports_bucket_arn" {
  value = aws_s3_bucket.reports.arn
}
