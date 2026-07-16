variable "project_name" {
  type        = string
  description = "Project prefix for resources"
  default     = "marketpulse"
}

variable "aws_region" {
  type        = string
  description = "AWS Region to deploy resources"
  default     = "us-east-1"
}

variable "data_lake_bucket_name" {
  type        = string
  description = "Globally unique name for the S3 data lake bucket"
  default     = "marketpulse-datalake-husnain"
}

variable "ssh_public_key" {
  type        = string
  description = "SSH public key to log into the EC2 instance host"
}

variable "tags" {
  type        = map(string)
  description = "Resource tags"
  default = {
    Environment = "Development"
    Project     = "MarketPulse"
    Owner       = "Intern B"
    IaC         = "Terraform"
  }
}
