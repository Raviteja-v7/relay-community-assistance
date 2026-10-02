variable "distribution_name" {
  description = "Description/name for the CloudFront distribution."
  type        = string
}

variable "bucket_name" {
  description = "S3 bucket name for the private frontend origin."
  type        = string
}

variable "bucket_arn" {
  description = "S3 bucket ARN for the CloudFront origin access policy."
  type        = string
}

variable "bucket_regional_domain_name" {
  description = "S3 regional domain name for the private frontend origin."
  type        = string
}

variable "tags" {
  description = "Tags applied to CloudFront resources."
  type        = map(string)
  default     = {}
}
