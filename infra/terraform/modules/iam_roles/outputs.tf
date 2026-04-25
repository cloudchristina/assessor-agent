output "lambda_role_arns" {
  description = "Map of logical lambda name (snake_case) to execution-role ARN."
  value       = { for k, r in aws_iam_role.lambda : k => r.arn }
}

output "lambda_role_arn_list" {
  description = "Flat list of all Lambda role ARNs — feed into kms.additional_principals."
  value       = [for r in aws_iam_role.lambda : r.arn]
}

output "step_functions_role_arn" {
  value = aws_iam_role.step_functions.arn
}
