variable "api_name" {
  description = "Name of the Relay HTTP API."
  type        = string
}

variable "lambda_function_name" {
  description = "Lambda function name for invoke permission."
  type        = string
}

variable "lambda_invoke_arn" {
  description = "Lambda invoke ARN for the HTTP API proxy integration."
  type        = string
}

variable "jwt_issuer" {
  type        = string
  description = "Cognito JWT issuer URL."
}

variable "jwt_audience" {
  type        = string
  description = "Cognito browser app client ID accepted by the authorizer."
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention for API access logs."
  type        = number
  default     = 30
}

variable "throttling_rate_limit" {
  description = "Steady-state API request limit per second."
  type        = number
  default     = 20
}

variable "throttling_burst_limit" {
  description = "Maximum short API request burst."
  type        = number
  default     = 40
}

variable "tags" {
  description = "Tags applied to API Gateway resources."
  type        = map(string)
  default     = {}
}
