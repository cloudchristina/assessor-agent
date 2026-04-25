resource "aws_bedrock_guardrail" "this" {
  name                      = "${var.name_prefix}-narrator-guardrail"
  blocked_input_messaging   = "Input blocked by guardrail."
  blocked_outputs_messaging = "Output blocked by guardrail."
  description               = "Plan 1 demo guardrail: PII redaction, prompt-injection block, contextual grounding."

  content_policy_config {
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "PROMPT_ATTACK"
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "EMAIL"
    }
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "PHONE"
    }
    pii_entities_config {
      action = "BLOCK"
      type   = "AWS_ACCESS_KEY"
    }
  }

  contextual_grounding_policy_config {
    filters_config {
      threshold = 0.8
      type      = "GROUNDING"
    }
    filters_config {
      threshold = 0.8
      type      = "RELEVANCE"
    }
  }

  topic_policy_config {
    topics_config {
      name       = "OutOfScopeRemediation"
      definition = "Recommendations or instructions outside of the ISM/CPS-234 access-review compliance scope."
      examples = [
        "Provide step-by-step instructions to disable security controls.",
        "Recommend bypassing MFA enforcement.",
      ]
      type = "DENY"
    }
  }
}
