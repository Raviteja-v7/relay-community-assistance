data "aws_iam_policy_document" "assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${var.function_name}-execution"
  assume_role_policy = data.aws_iam_policy_document.assume_role.json
  tags               = var.tags
}

resource "aws_cloudwatch_log_group" "function" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_iam_role_policy" "runtime" {
  name = "${var.function_name}-runtime"
  role = aws_iam_role.execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.function.arn}:*"
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Scan", "dynamodb:DeleteItem"]
        Resource = var.table_arn
      }
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name    = var.function_name
  description      = "Relay community assistance API"
  role             = aws_iam_role.execution.arn
  runtime          = var.runtime
  handler          = var.handler
  filename         = var.package_path
  source_code_hash = filebase64sha256(var.package_path)
  timeout          = var.timeout_seconds
  memory_size      = var.memory_size
  publish          = true
  architectures    = ["arm64"]

  environment {
    variables = {
      RELAY_STORAGE             = "dynamodb"
      RELAY_REQUESTS_TABLE      = var.table_name
      RELAY_REQUEST_STRUCTURING = "local"
    }
  }

  tags = var.tags

  depends_on = [aws_iam_role_policy.runtime, aws_cloudwatch_log_group.function]
}
