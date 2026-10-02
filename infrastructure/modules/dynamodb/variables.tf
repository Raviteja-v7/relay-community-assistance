variable "table_name" {
  description = "Name of the single-table Relay DynamoDB table."
  type        = string
}

variable "tags" {
  description = "Tags applied to the table."
  type        = map(string)
  default     = {}
}
