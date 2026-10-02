output "user_pool_id" {
  value       = aws_cognito_user_pool.users.id
  description = "Cognito user pool ID."
}

output "app_client_id" {
  value       = aws_cognito_user_pool_client.web.id
  description = "Public browser app client ID; it has no client secret."
}

output "issuer" {
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.users.id}"
  description = "JWT issuer URL used by API Gateway."
}

output "domain" {
  value       = "https://${aws_cognito_user_pool_domain.managed_login.domain}.auth.${var.aws_region}.amazoncognito.com"
  description = "Cognito managed login domain."
}
