output "function_arns" {
  description = "Logical lambda name -> Lambda function ARN."
  value       = { for k, m in module.fn : k => m.lambda_function_arn }
}

output "function_names" {
  value = { for k, m in module.fn : k => m.lambda_function_name }
}

output "dlq_arns" {
  value = { for k, q in aws_sqs_queue.dlq : k => q.arn }
}
