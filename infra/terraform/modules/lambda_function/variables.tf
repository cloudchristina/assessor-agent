variable "name" {
  type        = string
  description = "Logical function name, e.g. assessor-agent-dev-extract-uar."
}

variable "handler" {
  type        = string
  description = "Python entry point, e.g. extract_uar.handler.lambda_handler."
}

variable "source_s3_bucket" {
  type = string
}

variable "source_s3_key" {
  type = string
}

variable "source_code_hash" {
  type        = string
  description = "filebase64sha256 of the on-disk zip so Terraform redeploys on content change."
}

variable "role_arn" {
  type = string
}

variable "env" {
  type    = map(string)
  default = {}
}

variable "memory" {
  type    = number
  default = 1024
}

variable "timeout" {
  type    = number
  default = 60
}

variable "layers" {
  type    = list(string)
  default = []
}

variable "reserved_concurrency" {
  type    = number
  default = -1
}

variable "name_prefix" {
  type        = string
  description = "Project-environment prefix for DLQ naming."
}
