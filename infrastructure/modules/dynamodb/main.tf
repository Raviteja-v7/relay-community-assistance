resource "aws_dynamodb_table" "requests" {
  name                        = var.table_name
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "PK"
  deletion_protection_enabled = true

  attribute {
    name = "PK"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = var.tags

  lifecycle {
    prevent_destroy = true
  }
}
