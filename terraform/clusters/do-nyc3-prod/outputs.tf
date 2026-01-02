# Cluster outputs

output "cluster_id" {
  description = "DOKS cluster ID"
  value       = digitalocean_kubernetes_cluster.main.id
}

output "cluster_name" {
  description = "Cluster name"
  value       = digitalocean_kubernetes_cluster.main.name
}

output "cluster_endpoint" {
  description = "Kubernetes API server endpoint"
  value       = digitalocean_kubernetes_cluster.main.endpoint
}

output "cluster_urn" {
  description = "Cluster URN for use with other DO resources"
  value       = digitalocean_kubernetes_cluster.main.urn
}

output "kubeconfig" {
  description = "Kubeconfig for cluster access"
  value       = digitalocean_kubernetes_cluster.main.kube_config[0].raw_config
  sensitive   = true
}

output "vpc_id" {
  description = "VPC ID"
  value       = digitalocean_vpc.main.id
}

output "vpc_urn" {
  description = "VPC URN"
  value       = digitalocean_vpc.main.urn
}
