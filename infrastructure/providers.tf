provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Relay"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}
