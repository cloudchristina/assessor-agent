output "name_prefix" {
  value = local.name_prefix
}

output "state_machine_arn" {
  value = module.step_functions.state_machine_arn
}

output "runs_bucket_name" {
  value = module.s3_buckets.runs_bucket_name
}

output "reports_bucket_name" {
  value = module.s3_buckets.reports_bucket_name
}

output "runs_table_name" {
  value = module.dynamodb.runs_table_name
}

output "findings_table_name" {
  value = module.dynamodb.findings_table_name
}

output "guardrail_id" {
  value = module.bedrock_guardrail.guardrail_id
}
