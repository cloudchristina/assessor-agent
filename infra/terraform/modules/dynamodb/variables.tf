variable "name_prefix" {
  type = string
}

variable "kms_key_arn" {
  type        = string
  description = "CMK used to SSE-encrypt the tables."
}
