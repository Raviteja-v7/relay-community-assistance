variable "aws_region" {
  description = "AWS region for the API, Lambda, and DynamoDB resources."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name used in resource names."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z0-9-]{1,12}$", var.environment))
    error_message = "environment must use 1-12 lowercase letters, numbers, or hyphens."
  }
}

variable "lambda_package_path" {
  description = "Lambda package path relative to the infrastructure directory."
  type        = string
  default     = "../backend/relay_lambda.zip"
}
