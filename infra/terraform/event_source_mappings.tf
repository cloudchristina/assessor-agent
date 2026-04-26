# DDB Streams → Lambda event source mappings for Layer-5 eval Lambdas.
#
# shadow_eval   : triggered by INSERT events on the runs table stream.
# reviewer_disagreement : triggered by MODIFY events on the findings table stream.

resource "aws_lambda_event_source_mapping" "shadow_eval_runs_stream" {
  event_source_arn       = module.dynamodb.runs_stream_arn
  function_name          = module.lambda_artefacts.function_arns["shadow_eval"]
  starting_position      = "LATEST"
  batch_size             = 10
  maximum_retry_attempts = 3

  filter_criteria {
    filter {
      pattern = jsonencode({ eventName = ["INSERT"] })
    }
  }
}

resource "aws_lambda_event_source_mapping" "reviewer_disagreement_findings_stream" {
  event_source_arn       = module.dynamodb.findings_stream_arn
  function_name          = module.lambda_artefacts.function_arns["reviewer_disagreement"]
  starting_position      = "LATEST"
  batch_size             = 10
  maximum_retry_attempts = 3

  filter_criteria {
    filter {
      pattern = jsonencode({ eventName = ["MODIFY"] })
    }
  }
}
