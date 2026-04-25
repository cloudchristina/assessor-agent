output "secret_arns" {
  description = "List of ARNs, suitable for SECRETS_MANAGER_ARNS env var."
  value       = [for s in aws_secretsmanager_secret.this : s.arn]
}
