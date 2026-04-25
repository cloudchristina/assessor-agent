output "runs_table_name" {
  value = aws_dynamodb_table.runs.name
}

output "runs_table_arn" {
  value = aws_dynamodb_table.runs.arn
}

output "findings_table_name" {
  value = aws_dynamodb_table.findings.name
}

output "findings_table_arn" {
  value = aws_dynamodb_table.findings.arn
}
