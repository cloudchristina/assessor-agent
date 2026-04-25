variable "region" {
  type    = string
  default = "ap-southeast-2"
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev|staging|prod"
  }
}

variable "owner_email" { type = string }

variable "weekly_cron" {
  type        = string
  default     = "cron(0 9 ? * FRI *)"
  description = "EventBridge cron, AEST"
}

variable "monthly_cron" {
  type    = string
  default = "cron(0 9 1 * ? *)"
}

variable "adot_python_layer_arn" {
  type        = string
  description = "AWS-managed ADOT Python ARM64 Lambda layer ARN. Region-pinned. Catalogue: https://aws-otel.github.io/docs/getting-started/lambda/lambda-python"
  # ap-southeast-2 / Python / arm64 / latest stable as of writing.
  # Bump via tfvars without changing module code.
  default = "arn:aws:lambda:ap-southeast-2:901920570463:layer:aws-otel-python-arm64-ver-1-32-0:1"
}
