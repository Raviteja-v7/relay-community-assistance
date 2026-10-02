output "api_url" {
  description = "Public API Gateway HTTP API endpoint."
  value       = module.api_gateway.api_url
}

output "cloudfront_url" {
  description = "Public HTTPS frontend URL."
  value       = "https://${module.cloudfront.distribution_domain_name}"
}

output "s3_bucket" {
  description = "Private S3 bucket serving the frontend through CloudFront."
  value       = module.s3.bucket_name
}

output "dynamodb_table" {
  description = "Single DynamoDB table for requests, profiles, volunteers, reports, and blocks."
  value       = module.dynamodb.table_name
}

output "lambda_function" {
  description = "Relay API Lambda function name."
  value       = module.lambda.function_name
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool used for verified Relay accounts."
  value       = module.cognito.user_pool_id
}

output "cognito_app_client_id" {
  description = "Public Cognito web app client ID."
  value       = module.cognito.app_client_id
}

output "cognito_domain" {
  description = "Cognito managed login domain."
  value       = module.cognito.domain
}
