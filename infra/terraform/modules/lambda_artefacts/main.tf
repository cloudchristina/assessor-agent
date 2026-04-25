locals {
  by_name = { for l in var.lambdas : l.name => l }
}

module "package" {
  source   = "terraform-aws-modules/lambda/aws"
  version  = "~> 7.0"
  for_each = local.by_name

  function_name   = "${each.key}-package-only"
  create_function = false
  create_package  = true
  source_path = [
    { path = "${var.src_root}/${each.value.handler_dir}", prefix_in_zip = "" },
    { path = "${var.src_root}/shared", prefix_in_zip = "shared" },
  ]
  store_on_s3 = true
  s3_bucket   = var.deploy_bucket
}
