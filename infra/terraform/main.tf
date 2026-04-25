# Root composition.
#
# Dependency order:
#   kms -> s3_buckets, dynamodb, secrets -> iam_roles
#                                         -> bedrock_guardrail
#                                         -> lambda_artefacts
#                                         -> lambda_function (x10)
#                                         -> step_functions
#                                         -> eventbridge
#
# KMS-IAM circular dependency: the Lambda execution roles must appear as
# principals in the KMS key policies. We resolve this by:
#   1. Creating the KMS module with only account-root principals first.
#   2. Creating the iam_roles module (which needs the KMS ARNs) once those
#      keys exist.
#   3. Re-applying the KMS key policies via a follow-up
#      aws_kms_key_policy resource here in main.tf, after iam_roles has
#      produced role ARNs.

locals {
  lambda_defs = [
    { name = "extract_uar", handler_dir = "extract_uar" },
    { name = "validate_and_hash", handler_dir = "validate_and_hash" },
    { name = "rules_engine", handler_dir = "rules_engine" },
    { name = "agent_narrator", handler_dir = "agent_narrator" },
    { name = "citation_gate", handler_dir = "citation_gate" },
    { name = "reconciliation_gate", handler_dir = "reconciliation_gate" },
    { name = "entity_grounding_gate", handler_dir = "entity_grounding_gate" },
    { name = "judge", handler_dir = "judge" },
    { name = "publish_triage", handler_dir = "publish_triage" },
    { name = "generate_pdf", handler_dir = "generate_pdf" },
  ]

  handler_entry = {
    extract_uar           = "extract_uar.handler.lambda_handler"
    validate_and_hash     = "validate_and_hash.handler.lambda_handler"
    rules_engine          = "rules_engine.handler.lambda_handler"
    agent_narrator        = "agent_narrator.handler.lambda_handler"
    citation_gate         = "citation_gate.handler.lambda_handler"
    reconciliation_gate   = "reconciliation_gate.handler.lambda_handler"
    entity_grounding_gate = "entity_grounding_gate.handler.lambda_handler"
    judge                 = "judge.handler.lambda_handler"
    publish_triage        = "publish_triage.handler.lambda_handler"
    generate_pdf          = "generate_pdf.handler.lambda_handler"
  }

  src_root = "${path.module}/../../src"
}

module "kms" {
  source      = "./modules/kms"
  name_prefix = local.name_prefix
}

module "s3_buckets" {
  source              = "./modules/s3_buckets"
  name_prefix         = local.name_prefix
  raw_kms_key_arn     = module.kms.key_arns["raw"]
  reports_kms_key_arn = module.kms.key_arns["reports"]
}

module "dynamodb" {
  source      = "./modules/dynamodb"
  name_prefix = local.name_prefix
  kms_key_arn = module.kms.key_arns["findings"]
}

module "secrets" {
  source      = "./modules/secrets"
  name_prefix = local.name_prefix
  kms_key_arn = module.kms.key_arns["findings"]
  servers     = []
}

module "bedrock_guardrail" {
  source      = "./modules/bedrock_guardrail"
  name_prefix = local.name_prefix
}

module "iam_roles" {
  source             = "./modules/iam_roles"
  name_prefix        = local.name_prefix
  runs_bucket_arn    = module.s3_buckets.runs_bucket_arn
  reports_bucket_arn = module.s3_buckets.reports_bucket_arn
  runs_table_arn     = module.dynamodb.runs_table_arn
  findings_table_arn = module.dynamodb.findings_table_arn
  secret_arns        = module.secrets.secret_arns
  kms_raw_arn        = module.kms.key_arns["raw"]
  kms_findings_arn   = module.kms.key_arns["findings"]
  kms_reports_arn    = module.kms.key_arns["reports"]
  guardrail_arn      = module.bedrock_guardrail.guardrail_arn
}

module "lambda_artefacts" {
  source        = "./modules/lambda_artefacts"
  deploy_bucket = module.s3_buckets.runs_bucket_name
  src_root      = local.src_root
  lambdas       = local.lambda_defs
}

module "lambda_function" {
  source           = "./modules/lambda_function"
  for_each         = toset([for d in local.lambda_defs : d.name])
  name             = "${local.name_prefix}-${replace(each.key, "_", "-")}"
  name_prefix      = local.name_prefix
  handler          = local.handler_entry[each.key]
  source_s3_bucket = module.lambda_artefacts.artefacts[each.key].bucket
  source_s3_key    = module.lambda_artefacts.artefacts[each.key].key
  source_code_hash = module.lambda_artefacts.artefacts[each.key].sha256
  role_arn         = module.iam_roles.lambda_role_arns[each.key]
  env = merge(
    {
      POWERTOOLS_SERVICE_NAME = each.key
      RUNS_BUCKET             = module.s3_buckets.runs_bucket_name
    },
    each.key == "extract_uar" ? {
      SECRETS_MANAGER_ARNS = jsonencode(module.secrets.secret_arns)
    } : {},
    contains(["agent_narrator", "publish_triage"], each.key) ? {
      FINDINGS_TABLE = module.dynamodb.findings_table_name
    } : {},
    each.key == "publish_triage" ? {
      RUNS_TABLE = module.dynamodb.runs_table_name
    } : {},
    each.key == "agent_narrator" ? {
      BEDROCK_GUARDRAIL_ID = module.bedrock_guardrail.guardrail_id
    } : {},
  )
}

module "step_functions" {
  source          = "./modules/step_functions"
  name_prefix     = local.name_prefix
  role_arn        = module.iam_roles.step_functions_role_arn
  definition_path = "${path.module}/../step_functions/pipeline.asl.json"
  lambda_arns     = { for k, m in module.lambda_function : k => m.function_arn }
}

module "eventbridge" {
  source            = "./modules/eventbridge"
  name_prefix       = local.name_prefix
  state_machine_arn = module.step_functions.state_machine_arn
  weekly_cron       = var.weekly_cron
  monthly_cron      = var.monthly_cron
}
