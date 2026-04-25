locals {
  by_name = { for s in var.servers : s.name => s }
}

resource "aws_secretsmanager_secret" "this" {
  for_each   = local.by_name
  name       = "${var.name_prefix}/sql/${each.key}"
  kms_key_id = var.kms_key_arn
}

resource "aws_secretsmanager_secret_version" "placeholder" {
  for_each  = local.by_name
  secret_id = aws_secretsmanager_secret.this[each.key].id
  secret_string = jsonencode({
    host      = each.value.host
    port      = tostring(each.value.port)
    username  = each.value.username
    password  = "REPLACE_OUT_OF_BAND"
    databases = each.value.databases
  })
}
