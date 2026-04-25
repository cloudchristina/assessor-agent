variable "name_prefix" {
  type = string
}

variable "kms_key_arn" {
  type = string
}

variable "servers" {
  type = list(object({
    name      = string
    host      = string
    port      = number
    username  = string
    databases = string
  }))
  default     = []
  description = "One secret per entry. Password is a placeholder — rotate out-of-band."
}
