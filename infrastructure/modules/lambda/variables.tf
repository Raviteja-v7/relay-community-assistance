variable "function_name" {
  description = "Name of the Relay API Lambda function."
  type        = string
}

variable "table_name" {
  description = "Single-table DynamoDB name provided to the repositories."
  type        = string
}

variable "table_arn" {
  description = "Single-table DynamoDB ARN for least-privilege permissions."
  type        = string
}

variable "package_path" {
  description = "Path to the packaged backend Lambda zip."
  type        = string
}

variable "handler" {
  description = "Python Lambda entry point."
  type        = string
  default     = "app.api.handler.handler"
}

variable "runtime" {
  description = "Python Lambda runtime."
  type        = string
  default     = "python3.12"
}

variable "timeout_seconds" {
  description = "Maximum duration for an API invocation."
  type        = number
  default     = 15
}

variable "memory_size" {
  description = "Lambda memory in MiB."
  type        = number
  default     = 256
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for the function."
  type        = number
  default     = 30
}

variable "tags" {
  description = "Tags applied to Lambda and IAM resources."
  type        = map(string)
  default     = {}
}
