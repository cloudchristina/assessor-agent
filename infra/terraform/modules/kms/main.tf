data "aws_caller_identity" "current" {}

locals {
  cmks = ["raw", "findings", "reports"]
}

data "aws_iam_policy_document" "key" {
  for_each = toset(local.cmks)

  statement {
    sid     = "AccountRoot"
    effect  = "Allow"
    actions = ["kms:*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
    resources = ["*"]
  }

  dynamic "statement" {
    for_each = length(var.additional_principals) > 0 ? [1] : []
    content {
      sid    = "LambdaPrincipals"
      effect = "Allow"
      actions = [
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:ReEncrypt*",
        "kms:GenerateDataKey*",
        "kms:DescribeKey",
      ]
      principals {
        type        = "AWS"
        identifiers = var.additional_principals
      }
      resources = ["*"]
    }
  }
}

resource "aws_kms_key" "this" {
  for_each                = toset(local.cmks)
  description             = "${var.name_prefix}-${each.key} CMK"
  enable_key_rotation     = true
  deletion_window_in_days = 7
  policy                  = data.aws_iam_policy_document.key[each.key].json
}

resource "aws_kms_alias" "this" {
  for_each      = toset(local.cmks)
  name          = "alias/${var.name_prefix}-${each.key}"
  target_key_id = aws_kms_key.this[each.key].key_id
}
