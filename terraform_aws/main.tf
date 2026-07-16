# ─── Terraform Configuration ──────────────────────────────────────────────────
# Provider and version configuration for minimal AWS deployment.

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
  region = var.aws_region
}

# ─── VPC & Networking ────────────────────────────────────────────────────────
# Simple VPC setup to run our Airflow Host VM.

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-vpc"
  })
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.aws_region}a"

  tags = merge(var.tags, {
    Name = "${var.project_name}-public-subnet"
  })
}

resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id

  tags = merge(var.tags, {
    Name = "${var.project_name}-igw"
  })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-public-rt"
  })
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ─── Security Group ───────────────────────────────────────────────────────────
# Allow SSH access and Airflow UI access (port 8080) for the demo.

resource "aws_security_group" "airflow_sg" {
  name        = "${var.project_name}-airflow-sg"
  description = "Security group for Airflow VM Host"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH access"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # Lock down to specific IP in production
  }

  ingress {
    description = "Airflow Web UI"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "MLflow Web UI"
    from_port   = 5000
    to_port     = 5000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

# ─── Amazon S3 Data Lake (Minimal Medallion Storage) ─────────────────────────

resource "aws_s3_bucket" "data_lake" {
  bucket        = var.data_lake_bucket_name
  force_destroy = true # Allows clean tear down after the demo

  tags = var.tags
}

# Directories inside S3 (represented by empty folders)
resource "aws_s3_object" "bronze_folder" {
  bucket = aws_s3_bucket.data_lake.id
  key    = "bronze/"
}

resource "aws_s3_object" "silver_folder" {
  bucket = aws_s3_bucket.data_lake.id
  key    = "silver/"
}

resource "aws_s3_object" "gold_folder" {
  bucket = aws_s3_bucket.data_lake.id
  key    = "gold/"
}

# ─── Airflow VM Host (EC2 Instance) ───────────────────────────────────────────

# Lookup latest Ubuntu 22.04 AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
  owners = ["099720109477"] # Canonical
}

# Create SSH Key Pair
resource "aws_key_pair" "deployer" {
  key_name   = "${var.project_name}-key"
  public_key = var.ssh_public_key
}

resource "aws_instance" "airflow_host" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t2.micro" # Free Tier eligible (750 hrs/month free)
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.airflow_sg.id]
  key_name               = aws_key_pair.deployer.key_name

  # Provisioning block to install Docker, Docker Compose, and setup Airflow
  user_data = <<-EOF
              #!/bin/bash
              apt-get update -y
              apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
              
              # Install Docker
              mkdir -p /etc/apt/keyrings
              curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
              echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
              apt-get update -y
              apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
              
              systemctl enable docker
              systemctl start docker
              
              # Enable user execution permissions
              usermod -aG docker ubuntu
              EOF

  tags = merge(var.tags, {
    Name = "${var.project_name}-airflow-host"
  })
}

# ─── AWS Kinesis Data Stream ─────────────────────────────────────────────────
# Ingests live Alpaca stock and crypto price ticks in real-time.
# On-Demand mode: no shard provisioning needed, scales automatically.

resource "aws_kinesis_stream" "market_ticks" {
  name             = "${var.project_name}-market-ticks"
  stream_mode_details {
    stream_mode = "ON_DEMAND"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-market-ticks"
  })
}

# ─── AWS Glue Catalog Database ────────────────────────────────────────────────
# Acts as the schema registry for our S3 Delta Lake tables.
# Databricks can read table schemas directly from the Glue Catalog.

resource "aws_glue_catalog_database" "marketpulse_db" {
  name        = "marketpulse_lakehouse"
  description = "Glue Catalog database for MarketPulse Bronze/Silver/Gold layers"
}

# Glue Crawler IAM role — allows Glue to scan S3 and update the catalog
resource "aws_iam_role" "glue_crawler_role" {
  name = "${var.project_name}-glue-crawler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "glue_service_policy" {
  role       = aws_iam_role.glue_crawler_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_s3_access" {
  name = "${var.project_name}-glue-s3-access"
  role = aws_iam_role.glue_crawler_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.data_lake.arn,
        "${aws_s3_bucket.data_lake.arn}/*"
      ]
    }]
  })
}

# ─── IAM Role for Databricks to access S3 ────────────────────────────────────
# Databricks uses this role via instance profile to read/write
# Bronze, Silver, and Gold layers in S3 without hardcoded credentials.

resource "aws_iam_role" "databricks_s3_role" {
  name = "${var.project_name}-databricks-s3-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "databricks_s3_policy" {
  name = "${var.project_name}-databricks-s3-policy"
  role = aws_iam_role.databricks_s3_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["kinesis:GetRecords", "kinesis:GetShardIterator", "kinesis:DescribeStream", "kinesis:ListStreams"]
        Resource = aws_kinesis_stream.market_ticks.arn
      }
    ]
  })
}

resource "aws_iam_instance_profile" "databricks_profile" {
  name = "${var.project_name}-databricks-profile"
  role = aws_iam_role.databricks_s3_role.name
}

# ─── DynamoDB — Online Feature Store ─────────────────────────────────────────
# Caches the latest technical indicators per ticker symbol.
# Used by the SageMaker/prediction endpoint for <10ms feature lookups.

resource "aws_dynamodb_table" "feature_store" {
  name         = "${var.project_name}-feature-store"
  billing_mode = "PAY_PER_REQUEST" # No provisioned capacity cost
  hash_key     = "symbol"
  range_key    = "date"

  attribute {
    name = "symbol"
    type = "S"
  }

  attribute {
    name = "date"
    type = "S"
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-feature-store"
  })
}
