# Root composition.
#
# Dependency order:
#   kms -> s3_buckets, dynamodb, secrets -> iam_roles
#                                         -> bedrock_guardrail
#                                         -> lambda_artefacts (packages + creates 10 fns)
#                                         -> step_functions
#                                         -> eventbridge

locals {
  src_root          = "${path.module}/../../src"
  requirements_path = "${path.module}/lambda-requirements.txt"

  # One source-of-truth map keyed by logical (snake_case) lambda name.
  # handler entries use src.<dir>.handler.lambda_handler because the
  # packaging step puts everything under a `src/` prefix in the zip.
  lambda_specs = {
    extract_uar = {
      handler = "src.extract_uar.handler.lambda_handler"
      memory  = 1024
      timeout = 120
    }
    validate_and_hash = {
      handler = "src.validate_and_hash.handler.lambda_handler"
      memory  = 1024
      timeout = 60
    }
    rules_engine = {
      handler = "src.rules_engine.handler.lambda_handler"
      memory  = 1024
      timeout = 60
    }
    agent_narrator = {
      handler = "src.agent_narrator.handler.lambda_handler"
      memory  = 1024
      timeout = 300
    }
    citation_gate = {
      handler = "src.citation_gate.handler.lambda_handler"
      memory  = 512
      timeout = 30
    }
    reconciliation_gate = {
      handler = "src.reconciliation_gate.handler.lambda_handler"
      memory  = 512
      timeout = 30
    }
    entity_grounding_gate = {
      handler = "src.entity_grounding_gate.handler.lambda_handler"
      memory  = 512
      timeout = 30
    }
    judge = {
      handler = "src.judge.handler.lambda_handler"
      memory  = 1024
      timeout = 120
    }
    publish_triage = {
      handler = "src.publish_triage.handler.lambda_handler"
      memory  = 1024
      timeout = 60
    }
    generate_pdf = {
      handler = "src.generate_pdf.handler.lambda_handler"
      memory  = 1024
      timeout = 60
    }
    adversarial_probe = {
      handler = "src.adversarial_probe.handler.lambda_handler"
      memory  = 1024
      timeout = 60
    }
    reviewer_disagreement_digest = {
      handler = "src.reviewer_disagreement_digest.handler.lambda_handler"
      memory  = 512
      timeout = 60
    }
    shadow_eval = {
      handler = "src.shadow_eval.handler.lambda_handler"
      memory  = 1024
      timeout = 60
    }
    canary_orchestrator = {
      handler = "src.canary_orchestrator.handler.lambda_handler"
      memory  = 512
      timeout = 120
    }
    drift_detector = {
      handler = "src.drift_detector.handler.lambda_handler"
      memory  = 512
      timeout = 60
    }
    reviewer_disagreement = {
      handler = "src.reviewer_disagreement.handler.lambda_handler"
      memory  = 512
      timeout = 60
    }
  }
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
  source                          = "./modules/iam_roles"
  name_prefix                     = local.name_prefix
  runs_bucket_arn                 = module.s3_buckets.runs_bucket_arn
  reports_bucket_arn              = module.s3_buckets.reports_bucket_arn
  runs_table_arn                  = module.dynamodb.runs_table_arn
  findings_table_arn              = module.dynamodb.findings_table_arn
  drift_signals_table_arn         = module.dynamodb.drift_signals_table_arn
  canary_results_table_arn        = module.dynamodb.canary_results_table_arn
  drift_baseline_table_arn        = module.dynamodb.drift_baseline_table_arn
  golden_set_candidates_table_arn = module.dynamodb.golden_set_candidates_table_arn
  secret_arns                     = module.secrets.secret_arns
  kms_raw_arn                     = module.kms.key_arns["raw"]
  kms_findings_arn                = module.kms.key_arns["findings"]
  kms_reports_arn                 = module.kms.key_arns["reports"]
  guardrail_arn                   = module.bedrock_guardrail.guardrail_arn
}

module "lambda_artefacts" {
  source            = "./modules/lambda_artefacts"
  name_prefix       = local.name_prefix
  deploy_bucket     = module.s3_buckets.runs_bucket_name
  src_root          = local.src_root
  requirements_path = local.requirements_path

  lambdas = {
    for k, spec in local.lambda_specs : k => {
      handler  = spec.handler
      role_arn = module.iam_roles.lambda_role_arns[k]
      memory   = spec.memory
      timeout  = spec.timeout
      # ADOT Python arm64 layer for OTel auto-instrumentation. Attached only
      # to Lambdas where Strands emits tool/model OTel spans we want to see in
      # X-Ray. Layer ARN is a sourceable AWS-managed layer; pin via
      # var.adot_python_layer_arn.
      layers = contains(["agent_narrator", "judge", "adversarial_probe", "shadow_eval"], k) ? [var.adot_python_layer_arn] : []
      env = merge(
        {
          POWERTOOLS_SERVICE_NAME = k
          RUNS_BUCKET             = module.s3_buckets.runs_bucket_name
        },
        k == "extract_uar" ? {
          SECRETS_MANAGER_ARNS  = jsonencode(module.secrets.secret_arns)
          SYNTHETIC_DATA_S3_URI = "s3://${module.s3_buckets.runs_bucket_name}/fixtures/synth.csv"
        } : {},
        contains(["agent_narrator", "publish_triage"], k) ? {
          FINDINGS_TABLE = module.dynamodb.findings_table_name
        } : {},
        k == "publish_triage" ? {
          RUNS_TABLE = module.dynamodb.runs_table_name
        } : {},
        # OTel manual init: Strands' transitive opentelemetry-* (1.41) doesn't
        # play nicely with the ADOT layer's older copies (1.32) when the
        # auto-instrumentation wrapper (AWS_LAMBDA_EXEC_WRAPPER) is active —
        # the wrapper crashes on a LogData ImportError. We therefore skip the
        # wrapper and configure the OTel SDK manually in src/shared/otel_init.py
        # using the zip's 1.41 SDK + an OTLP HTTP exporter targeting the ADOT
        # collector sidecar (still attached via the layer, listening on 4318).
        contains(["agent_narrator", "judge", "adversarial_probe", "shadow_eval"], k) ? {
          OTEL_SERVICE_NAME        = k
          OTEL_RESOURCE_ATTRIBUTES = "service.name=${k},service.namespace=assessor-agent"
          # NOTE: TRACES_ENDPOINT is the FULL URL — exporter does not append
          # `/v1/traces`. Using the path-less OTEL_EXPORTER_OTLP_ENDPOINT
          # would cause a 404 because the exporter appends `/v1/traces`,
          # producing `http://localhost:4318/v1/traces/v1/traces` if both
          # were set with paths.
          OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "http://localhost:4318/v1/traces"
          OTEL_PROPAGATORS                   = "xray,tracecontext"
        } : {},
        k == "agent_narrator" ? {
          BEDROCK_GUARDRAIL_ID = module.bedrock_guardrail.guardrail_id
          # Cross-region inference profile (Sydney). Sonnet 4.5 / 4.6
          # require a one-time Anthropic use-case form submission via the
          # Bedrock console (Model catalog -> select model -> Available
          # to request -> Request access). Haiku 4.5 is auto-enabled on
          # this account.
          BEDROCK_MODEL_ID = "au.anthropic.claude-sonnet-4-5-20250929-v1:0"
        } : {},
        k == "judge" ? {
          JUDGE_MODEL_ID = "au.anthropic.claude-haiku-4-5-20251001-v1:0"
        } : {},
        k == "adversarial_probe" ? {
          BEDROCK_MODEL_ID = "au.anthropic.claude-haiku-4-5-20251001-v1:0"
        } : {},
        k == "reviewer_disagreement_digest" ? {
          GOLDEN_SET_CANDIDATES_TABLE = "${local.name_prefix}-golden-set-candidates"
          DIGEST_FROM                 = var.owner_email
          COMPLIANCE_EMAIL            = var.owner_email
        } : {},
        k == "shadow_eval" ? {
          DRIFT_SIGNALS_TABLE    = module.dynamodb.drift_signals_table_name
          JUDGE_FUNCTION_NAME    = "${local.name_prefix}-judge"
          SHADOW_DRIFT_THRESHOLD = "0.10"
          BEDROCK_MODEL_ID       = "au.anthropic.claude-haiku-4-5-20251001-v1:0"
        } : {},
        k == "canary_orchestrator" ? {
          # Constructed to avoid a cycle: step_functions -> lambda_artefacts -> canary env -> step_functions.
          # The ARN is deterministic from name_prefix + account + region (all pre-apply).
          STATE_MACHINE_ARN      = "arn:aws:states:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:stateMachine:${local.name_prefix}-pipeline"
          CANARY_RESULTS_TABLE   = module.dynamodb.canary_results_table_name
          RUNS_TABLE             = module.dynamodb.runs_table_name
          SYNTHETIC_INPUT_BUCKET = module.s3_buckets.runs_bucket_name
        } : {},
        k == "drift_detector" ? {
          RUNS_TABLE          = module.dynamodb.runs_table_name
          DRIFT_SIGNALS_TABLE = module.dynamodb.drift_signals_table_name
          DRIFT_ALPHA         = "0.05"
        } : {},
        k == "reviewer_disagreement" ? {
          GOLDEN_SET_CANDIDATES_TABLE = module.dynamodb.golden_set_candidates_table_name
        } : {},
      )
    }
  }
}

module "step_functions" {
  source          = "./modules/step_functions"
  name_prefix     = local.name_prefix
  role_arn        = module.iam_roles.step_functions_role_arn
  definition_path = "${path.module}/../step_functions/pipeline.asl.json"
  lambda_arns     = module.lambda_artefacts.function_arns
}

module "eventbridge" {
  source                           = "./modules/eventbridge"
  name_prefix                      = local.name_prefix
  state_machine_arn                = module.step_functions.state_machine_arn
  weekly_cron                      = var.weekly_cron
  monthly_cron                     = var.monthly_cron
  reviewer_disagreement_digest_arn = module.lambda_artefacts.function_arns["reviewer_disagreement_digest"]
  canary_orchestrator_arn          = module.lambda_artefacts.function_arns["canary_orchestrator"]
  drift_detector_arn               = module.lambda_artefacts.function_arns["drift_detector"]
}

module "eval_alarms" {
  source                    = "./modules/eval_alarms"
  name_prefix               = local.name_prefix
  email                     = var.owner_email
  judge_log_group_name      = "/aws/lambda/${local.name_prefix}-judge"
  drift_signals_table_name  = module.dynamodb.drift_signals_table_name
  canary_results_table_name = module.dynamodb.canary_results_table_name
  tags                      = local.common_tags
}

module "bedrock_invocations" {
  source      = "./modules/bedrock_invocations"
  name_prefix = local.name_prefix
  # Let the module create its own KMS key; the existing keys (raw/findings/reports)
  # are scoped to pipeline data, not Bedrock invocation logs.
  kms_key_arn = ""
  tags        = local.common_tags
}

module "bedrock_logging_config" {
  source      = "./modules/bedrock_logging_config"
  bucket_arn  = module.bedrock_invocations.bucket_arn
  bucket_name = module.bedrock_invocations.bucket_name
}

module "aws_budgets" {
  source      = "./modules/aws_budgets"
  name_prefix = local.name_prefix
  email       = var.owner_email
  tags        = local.common_tags
}
