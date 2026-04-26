variable "name_prefix" {
  type        = string
  description = "Prefix used for function + DLQ naming, e.g. assessor-agent-dev."
}

variable "deploy_bucket" {
  type        = string
  description = "S3 bucket where Lambda zips are uploaded."
}

variable "src_root" {
  type        = string
  description = "Absolute path to the repo's src/ directory — ships under a `src/` prefix inside each zip so handler imports like `from src.shared.models import UARRow` resolve."
}

variable "evals_root" {
  type        = string
  description = "Absolute path to the repo's evals/ directory — ships under an `evals/` prefix inside each zip so handlers (e.g. canary_orchestrator) can read baselines + fixtures from /var/task/evals/."
}

variable "requirements_path" {
  type        = string
  description = "Absolute path to a requirements.txt listing runtime deps (pydantic, pymssql, strands-agents, ...). boto3 is provided by the Lambda runtime and MUST NOT be listed."
}

variable "lambdas" {
  type = map(object({
    handler  = string
    role_arn = string
    env      = map(string)
    memory   = number
    timeout  = number
    layers   = optional(list(string), [])
  }))
  description = "Keyed by logical lambda name (snake_case). env is passed through to Lambda config. layers is an optional list of layer ARNs (e.g. the ADOT Python layer for OTel auto-instrumentation)."
}
