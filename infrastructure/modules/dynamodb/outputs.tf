output "table_name" {
  value = aws_dynamodb_table.requests.name
}

output "table_arn" {
  value = aws_dynamodb_table.requests.arn
}
