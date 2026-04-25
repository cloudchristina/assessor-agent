variable "name_prefix" {
  type = string
}

variable "role_arn" {
  type = string
}

variable "definition_path" {
  type        = string
  description = "Absolute path to the ASL JSON template (raw; $${...} placeholders rendered via templatefile)."
}

variable "lambda_arns" {
  type        = map(string)
  description = "Logical snake_case lambda name -> function ARN."
}

variable "log_group_kms_key_arn" {
  type    = string
  default = null
}
