output "key_arns" {
  description = "Map of CMK name (raw|findings|reports) to KMS key ARN."
  value       = { for k, v in aws_kms_key.this : k => v.arn }
}

output "key_ids" {
  description = "Map of CMK name to KMS key ID."
  value       = { for k, v in aws_kms_key.this : k => v.key_id }
}
