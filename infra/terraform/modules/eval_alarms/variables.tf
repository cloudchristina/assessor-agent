variable "name_prefix" {
  type        = string
  description = "Prefix applied to all resource names."
}

variable "email" {
  type        = string
  description = "SES recipient email address for alarm notifications."
}

variable "judge_log_group_name" {
  type        = string
  description = "CloudWatch log group for the judge Lambda (e.g. /aws/lambda/<prefix>-judge)."
}

variable "drift_signals_table_name" {
  type        = string
  description = "DynamoDB table name for shadow-eval drift signals."
}

variable "canary_results_table_name" {
  type        = string
  description = "DynamoDB table name for canary run results."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to all taggable resources."
}
