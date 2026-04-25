locals {
  project = "assessor-agent"
  common_tags = {
    project     = local.project
    environment = var.environment
    managed_by  = "terraform"
    owner       = var.owner_email
  }
  name_prefix = "${local.project}-${var.environment}"
}
