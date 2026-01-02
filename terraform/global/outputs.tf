output "tailscale_auth_keys" {
  description = "Tailscale auth keys for each cluster"
  value       = { for k, v in tailscale_tailnet_key.cluster : k => v.key }
  sensitive   = true
}
