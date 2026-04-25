output "function_arn" {
  value = aws_lambda_function.this.arn
}

output "function_name" {
  value = aws_lambda_function.this.function_name
}

output "dlq_arn" {
  value = aws_sqs_queue.dlq.arn
}
