variable "name_prefix" {
  type        = string
  description = "Project + environment prefix, e.g. assessor-agent-dev."
}

variable "email" {
  type        = string
  description = "Email address to receive budget alert notifications."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply to all resources in this module."
}
