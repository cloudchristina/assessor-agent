variable "name_prefix" {
  type = string
}

variable "raw_kms_key_arn" {
  type        = string
  description = "CMK used to SSE-encrypt the runs bucket."
}

variable "reports_kms_key_arn" {
  type        = string
  description = "CMK used to SSE-encrypt the reports bucket."
}

variable "object_lock_years" {
  type        = number
  default     = 7
  description = "Default Object Lock retention on the reports bucket."
}

variable "validated_expiration_days" {
  type        = number
  default     = 30
  description = "Lifecycle: expire validated/* after this many days."
}
