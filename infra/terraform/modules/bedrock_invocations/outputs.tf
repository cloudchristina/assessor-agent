output "bucket_name" {
  value       = aws_s3_bucket.bedrock_invocations.bucket
  description = "Name of the Bedrock invocation logs S3 bucket."
}

output "bucket_arn" {
  value       = aws_s3_bucket.bedrock_invocations.arn
  description = "ARN of the Bedrock invocation logs S3 bucket."
}

output "kms_key_arn" {
  value       = local.kms_arn
  description = "ARN of the KMS key used to encrypt the bucket (created or passed in)."
}
