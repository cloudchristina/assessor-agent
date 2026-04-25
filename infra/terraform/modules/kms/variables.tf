variable "name_prefix" {
  type        = string
  description = "Project + environment prefix, e.g. assessor-agent-dev."
}

variable "additional_principals" {
  type        = list(string)
  default     = []
  description = "IAM role/user ARNs to grant decrypt+encrypt on every CMK in this module. Used to break the iam_roles -> kms cycle (see main.tf comment)."
}
