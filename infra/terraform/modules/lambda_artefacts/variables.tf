variable "deploy_bucket" {
  type        = string
  description = "S3 bucket where Lambda zips will be uploaded."
}

variable "src_root" {
  type        = string
  description = "Absolute path to repo's src/ directory."
}

variable "lambdas" {
  type = list(object({
    name        = string
    handler_dir = string
  }))
}
