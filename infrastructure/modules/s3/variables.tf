variable "bucket_name" {
  description = "Globally unique name of the private frontend bucket."
  type        = string
}

variable "tags" {
  description = "Tags applied to the bucket."
  type        = map(string)
  default     = {}
}
