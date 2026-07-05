"""monitoring_servers role: central Prometheus + Grafana + image renderer.

The scrape target list (prometheus_scrape_targets) is host data: it names
concrete addresses, so it lives in the host dict in inventory.py.
"""

prometheus_enabled = True
grafana_enabled = True
grafana_image_renderer_enabled = True
monitoring_network_enabled = True
rendering_network_enabled = True
tailscale_serve_enabled = True
