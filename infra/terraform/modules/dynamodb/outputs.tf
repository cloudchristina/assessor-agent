output "runs_table_name" {
  value = aws_dynamodb_table.runs.name
}

output "runs_table_arn" {
  value = aws_dynamodb_table.runs.arn
}

output "runs_stream_arn" {
  value = aws_dynamodb_table.runs.stream_arn
}

output "findings_table_name" {
  value = aws_dynamodb_table.findings.name
}

output "findings_table_arn" {
  value = aws_dynamodb_table.findings.arn
}

output "findings_stream_arn" {
  value = aws_dynamodb_table.findings.stream_arn
}

output "eval_results_table_name" {
  value = aws_dynamodb_table.eval_results.name
}

output "eval_results_table_arn" {
  value = aws_dynamodb_table.eval_results.arn
}

output "drift_baseline_table_name" {
  value = aws_dynamodb_table.drift_baseline.name
}

output "drift_baseline_table_arn" {
  value = aws_dynamodb_table.drift_baseline.arn
}

output "golden_set_candidates_table_name" {
  value = aws_dynamodb_table.golden_set_candidates.name
}

output "golden_set_candidates_table_arn" {
  value = aws_dynamodb_table.golden_set_candidates.arn
}

output "canary_results_table_name" {
  value = aws_dynamodb_table.canary_results.name
}

output "canary_results_table_arn" {
  value = aws_dynamodb_table.canary_results.arn
}

output "drift_signals_table_name" {
  value = aws_dynamodb_table.drift_signals.name
}

output "drift_signals_table_arn" {
  value = aws_dynamodb_table.drift_signals.arn
}
