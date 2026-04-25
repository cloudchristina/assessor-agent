resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/stepfunctions/${var.name_prefix}"
  retention_in_days = 30
  kms_key_id        = var.log_group_kms_key_arn
}

locals {
  definition = templatefile(var.definition_path, {
    extract_uar_arn           = var.lambda_arns["extract_uar"]
    validate_and_hash_arn     = var.lambda_arns["validate_and_hash"]
    rules_engine_arn          = var.lambda_arns["rules_engine"]
    agent_narrator_arn        = var.lambda_arns["agent_narrator"]
    citation_gate_arn         = var.lambda_arns["citation_gate"]
    reconciliation_gate_arn   = var.lambda_arns["reconciliation_gate"]
    entity_grounding_gate_arn = var.lambda_arns["entity_grounding_gate"]
    judge_arn                 = var.lambda_arns["judge"]
    publish_triage_arn        = var.lambda_arns["publish_triage"]
    generate_pdf_arn          = var.lambda_arns["generate_pdf"]
  })
}

resource "aws_sfn_state_machine" "this" {
  name       = "${var.name_prefix}-pipeline"
  role_arn   = var.role_arn
  type       = "STANDARD"
  definition = local.definition

  logging_configuration {
    level                  = "ALL"
    include_execution_data = true
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
  }

  tracing_configuration {
    enabled = true
  }
}
