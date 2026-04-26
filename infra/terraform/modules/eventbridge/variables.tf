variable "name_prefix" {
  type = string
}

variable "state_machine_arn" {
  type = string
}

variable "weekly_cron" {
  type = string
}

variable "monthly_cron" {
  type = string
}

variable "reviewer_disagreement_digest_arn" {
  type        = string
  description = "ARN of the reviewer-disagreement-digest Lambda function."
}

variable "canary_orchestrator_arn" {
  type        = string
  description = "ARN of the canary-orchestrator Lambda function."
}

variable "drift_detector_arn" {
  type        = string
  description = "ARN of the drift-detector Lambda function."
}
