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

variable "drift_signals_table_arn" {
  type        = string
  description = "ARN of the drift-signals DynamoDB table."
}

variable "canary_results_table_arn" {
  type        = string
  description = "ARN of the canary-results DynamoDB table."
}

variable "drift_baseline_table_arn" {
  type        = string
  description = "ARN of the drift-baseline DynamoDB table."
}

variable "golden_set_candidates_table_arn" {
  type        = string
  description = "ARN of the golden-set-candidates DynamoDB table."
}

