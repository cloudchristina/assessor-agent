terraform {
  backend "s3" {
    # configure via -backend-config on init:
    # bucket="...", key="assessor-agent/terraform.tfstate", region="ap-southeast-2"
  }
}
