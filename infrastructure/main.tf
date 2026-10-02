data "aws_caller_identity" "current" {}

locals {
  name_prefix   = "relay-${var.environment}"
  frontend_dist = "${path.root}/../frontend/dist"
  frontend_files = toset([
    for file_name in fileset(local.frontend_dist, "**") : file_name
    if file_name != "config.js"
  ])
  tags = {
    Project     = "Relay"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
  mime_types = {
    css   = "text/css"
    html  = "text/html"
    ico   = "image/x-icon"
    js    = "text/javascript"
    json  = "application/json"
    png   = "image/png"
    svg   = "image/svg+xml"
    txt   = "text/plain"
    webp  = "image/webp"
    woff  = "font/woff"
    woff2 = "font/woff2"
  }
}

module "dynamodb" {
  source     = "./modules/dynamodb"
  table_name = "${local.name_prefix}-data"
  tags       = local.tags
}

module "lambda" {
  source        = "./modules/lambda"
  function_name = "${local.name_prefix}-api"
  package_path  = "${path.root}/${var.lambda_package_path}"
  table_name    = module.dynamodb.table_name
  table_arn     = module.dynamodb.table_arn
  tags          = local.tags
}

module "s3" {
  source      = "./modules/s3"
  bucket_name = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}-web"
  tags        = local.tags
}

module "cloudfront" {
  source                      = "./modules/cloudfront"
  distribution_name           = "${local.name_prefix}-frontend"
  bucket_name                 = module.s3.bucket_name
  bucket_arn                  = module.s3.bucket_arn
  bucket_regional_domain_name = module.s3.bucket_regional_domain_name
  tags                        = local.tags
}

module "cognito" {
  source        = "./modules/cognito"
  pool_name     = "${local.name_prefix}-users"
  domain_prefix = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}"
  callback_url  = "https://${module.cloudfront.distribution_domain_name}/"
  logout_url    = "https://${module.cloudfront.distribution_domain_name}/"
  aws_region    = var.aws_region
  tags          = local.tags
}

module "api_gateway" {
  source               = "./modules/api_gateway"
  api_name             = "${local.name_prefix}-http-api"
  lambda_function_name = module.lambda.function_name
  lambda_invoke_arn    = module.lambda.invoke_arn
  jwt_issuer           = module.cognito.issuer
  jwt_audience         = module.cognito.app_client_id
  tags                 = local.tags
}

resource "aws_s3_object" "frontend_asset" {
  for_each = local.frontend_files

  bucket        = module.s3.bucket_name
  key           = each.value
  source        = "${local.frontend_dist}/${each.value}"
  source_hash   = filemd5("${local.frontend_dist}/${each.value}")
  content_type  = lookup(local.mime_types, element(reverse(split(".", each.value)), 0), "application/octet-stream")
  cache_control = each.value == "index.html" ? "no-cache, no-store, must-revalidate" : "public, max-age=31536000, immutable"
}

resource "aws_s3_object" "frontend_runtime_config" {
  bucket        = module.s3.bucket_name
  key           = "config.js"
  content       = "window.RELAY_CONFIG = { apiBaseUrl: ${jsonencode(module.api_gateway.api_url)}, userPoolId: ${jsonencode(module.cognito.user_pool_id)}, userPoolClientId: ${jsonencode(module.cognito.app_client_id)}, cognitoDomain: ${jsonencode(module.cognito.domain)} };\n"
  content_type  = "text/javascript"
  cache_control = "no-cache, no-store, must-revalidate"
}
