resource "aws_bedrock_model_invocation_logging_configuration" "main" {
  logging_config {
    embedding_data_delivery_enabled = true
    image_data_delivery_enabled     = false
    text_data_delivery_enabled      = true
    s3_config {
      bucket_name = var.bucket_name
      key_prefix  = var.key_prefix
    }
  }
}
