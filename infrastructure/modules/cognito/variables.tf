variable "pool_name" {
  type        = string
  description = "Cognito user pool name."
}

variable "domain_prefix" {
  type        = string
  description = "Globally unique Cognito managed-login domain prefix."
}

variable "callback_url" {
  type        = string
  description = "Allowed browser OAuth callback URL."
}

variable "logout_url" {
  type        = string
  description = "Allowed browser logout return URL."
}

variable "aws_region" {
  type        = string
  description = "Region of the Cognito user pool."
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags applied to supported Cognito resources."
}
