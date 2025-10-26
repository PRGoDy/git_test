terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  type    = string
  default = "us-east-1"
}

resource "aws_iam_policy" "access_hub_boundary" {
  name        = "access-hub-boundary"
  description = "Restricts Access Hub delegated roles to approved actions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:*", "ec2:Describe*", "iam:Get*", "iam:List*"]
        Resource = "*"
      },
      {
        Effect   = "Deny"
        Action   = ["iam:CreateUser", "iam:CreateAccessKey"]
        Resource = "*"
      }
    ]
  })
}

output "permission_boundary_arn" {
  value = aws_iam_policy.access_hub_boundary.arn
}
