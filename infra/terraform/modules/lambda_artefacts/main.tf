# Unified Lambda module: package source + pip-install runtime deps + upload
# to S3 + create the function. Uses terraform-aws-modules/lambda/aws which
# handles the cross-platform pip install (host=darwin, target=Lambda arm64
# Linux) via --platform manylinux2014_aarch64 --only-binary=:all:.
#
# We pack the entire src/ tree under a `src/` prefix in every zip so the
# handlers' `from src.shared.X import Y` imports resolve at runtime. boto3
# is provided by the Lambda runtime and is intentionally excluded from
# requirements.txt.

resource "aws_sqs_queue" "dlq" {
  for_each                  = var.lambdas
  name                      = "${var.name_prefix}-${replace(each.key, "_", "-")}-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

module "fn" {
  source   = "terraform-aws-modules/lambda/aws"
  version  = "~> 7.0"
  for_each = var.lambdas

  function_name = "${var.name_prefix}-${replace(each.key, "_", "-")}"
  handler       = each.value.handler
  runtime       = "python3.13"
  architectures = ["arm64"]
  memory_size   = each.value.memory
  timeout       = each.value.timeout

  source_path = [
    {
      path          = var.src_root
      prefix_in_zip = "src"
    },
    {
      path             = var.requirements_path
      pip_requirements = true
    },
  ]

  store_on_s3 = true
  s3_bucket   = var.deploy_bucket
  s3_prefix   = "lambda/${each.key}/"

  create_role = false
  lambda_role = each.value.role_arn

  environment_variables = each.value.env

  tracing_mode = "Active"

  attach_dead_letter_policy = true
  dead_letter_target_arn    = aws_sqs_queue.dlq[each.key].arn

  cloudwatch_logs_retention_in_days = 30
}
