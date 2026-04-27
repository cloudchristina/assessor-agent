variable "name_prefix" {
  type        = string
  description = "Project + environment prefix, e.g. assessor-agent-dev."
}

variable "kms_key_arn" {
  type        = string
  default     = ""
  description = "ARN of an existing KMS key to use for SSE. If blank, a new key is created."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply to all resources in this module."
}
