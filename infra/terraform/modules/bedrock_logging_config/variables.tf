variable "bucket_arn" {
  type        = string
  description = "ARN of the S3 bucket that receives Bedrock invocation logs."
}

variable "bucket_name" {
  type        = string
  description = "Name of the S3 bucket that receives Bedrock invocation logs."
}

variable "key_prefix" {
  type        = string
  default     = "bedrock-invocations/"
  description = "S3 key prefix for Bedrock invocation log objects."
}
