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
