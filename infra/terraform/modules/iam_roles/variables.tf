variable "name_prefix" {
  type = string
}

variable "runs_bucket_arn" {
  type = string
}

variable "reports_bucket_arn" {
  type = string
}

variable "runs_table_arn" {
  type = string
}

variable "findings_table_arn" {
  type = string
}

variable "secret_arns" {
  type    = list(string)
  default = []
}

variable "kms_raw_arn" {
  type = string
}

variable "kms_findings_arn" {
  type = string
}

variable "kms_reports_arn" {
  type = string
}

variable "guardrail_arn" {
  type        = string
  default     = ""
  description = "Optional — empty string means no guardrail constraint on InvokeModel."
}
