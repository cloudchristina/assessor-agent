# VPC module — deferred for Plan 1

This directory is intentionally empty. For the Plan 1 meetup demo, every
Lambda runs **outside any VPC** and reaches Bedrock / S3 / DynamoDB / KMS /
Secrets Manager over the public AWS network.

## Why defer

- Interface endpoints cost ~$8/month each; the full set needed (Bedrock
  runtime, Secrets Manager, KMS, STS, CloudWatch Logs) would add ~$40/month
  before traffic, blowing the demo's "$5–$15 per month" budget target.
- VPC Lambdas require `ec2:CreateNetworkInterface` / `DescribeNetworkInterfaces`
  / `DeleteNetworkInterface` on the execution role.
- ENI attachment adds 5–10 seconds to cold-start latency, which is noticeable
  in a live demo.

## What to build when promoting to production

1. `main.tf` with `aws_vpc`, two private subnets in different AZs, no IGW
   and no NAT (Lambdas reach AWS services via endpoints only).
2. Interface endpoints for: `bedrock-runtime`, `secretsmanager`, `kms`, `sts`,
   `logs`, and any per-service endpoints the production pipeline adds.
3. Gateway endpoints for S3 and DynamoDB (free).
4. Security groups — one for the Lambda ENIs, one for each endpoint.
5. Add `AWSLambdaVPCAccessExecutionRole` (or equivalent inline policy) to
   every Lambda role in `modules/iam_roles`.
6. Pass `subnet_ids` and `security_group_ids` into `modules/lambda_function`
   and wire them onto `aws_lambda_function.vpc_config`.
7. Update `modules/iam_roles` to allow `ec2:*NetworkInterface*` on the
   Lambda execution roles.

Nothing in Plan 1 depends on this module existing.
