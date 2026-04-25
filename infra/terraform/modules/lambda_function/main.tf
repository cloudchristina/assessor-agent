resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-dlq"
  message_retention_seconds = 1209600 # 14 days
  sqs_managed_sse_enabled   = true
}

resource "aws_lambda_function" "this" {
  function_name = var.name
  role          = var.role_arn
  handler       = var.handler
  runtime       = "python3.13"
  architectures = ["arm64"]
  memory_size   = var.memory
  timeout       = var.timeout
  layers        = var.layers

  s3_bucket        = var.source_s3_bucket
  s3_key           = var.source_s3_key
  source_code_hash = var.source_code_hash

  reserved_concurrent_executions = var.reserved_concurrency

  tracing_config {
    mode = "Active"
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.dlq.arn
  }

  dynamic "environment" {
    for_each = length(var.env) > 0 ? [1] : []
    content {
      variables = var.env
    }
  }
}
