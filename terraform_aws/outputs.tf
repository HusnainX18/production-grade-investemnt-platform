output "vpc_id" {
  value       = aws_vpc.main.id
  description = "AWS VPC ID"
}

output "subnet_id" {
  value       = aws_subnet.public.id
  description = "AWS Public Subnet ID"
}

output "security_group_id" {
  value       = aws_security_group.airflow_sg.id
  description = "AWS Security Group ID for Airflow Host"
}

output "data_lake_bucket_name" {
  value       = aws_s3_bucket.data_lake.id
  description = "Name of the S3 Data Lake Bucket"
}

output "airflow_public_ip" {
  value       = aws_instance.airflow_host.public_ip
  description = "Public IP Address of the EC2 Airflow VM Host"
}

output "ssh_command" {
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_instance.airflow_host.public_ip}"
  description = "SSH Connection Command"
}
