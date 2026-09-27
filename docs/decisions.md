## 2026-09-27: Store bsync tenant data in Durable Objects

**Supersedes:** 2026-09-24, Manage bsync staging resources in global Terraform.

**Trigger:** The approved bsync design uses SQLite-backed Durable Objects and does not require D1.

**Decision:** Terraform owns Access applications, policies, DNS records, and Worker custom domains. Wrangler owns the Worker and Durable Object classes. Durable Objects store bsync tenant data in SQLite.

**Rejected:** Keep D1 as bsync tenant storage.

**Why:** Each tenant's Worker owns its SQLite-backed storage.

**Revisit when:** The bsync design adds a separate database service.

**Links:** `~/src/bsync/openspec/changes/privacy-first-sync-service/design.md`, `terraform/global/bsync.tf`.

## 2026-09-24: Manage bsync staging resources in global Terraform

**Context:** The global workspace manages the `bc4.uk` zone. bsync needs account login, D1, and a Worker custom domain.

**Decision:** Global Terraform owns the Cloudflare identity provider, bsync Access policy and application, D1 database, and custom domain. It reads the existing Zero Trust organization. Wrangler owns the Worker and Durable Object class.

**Rejected:** Dashboard-managed bsync Access. Wrangler-managed bsync custom domain. A second Zero Trust organization.

**Why:** The global workspace already manages `bc4.uk`. One owner per resource prevents route and policy drift.

**Revisit when:** bsync requires independent Terraform state or the provider cannot maintain Managed OAuth.

**Links:** `terraform/global/bsync.tf`, `~/src/bsync/wrangler.jsonc`.

## 2026-09-24: Manage bc4.uk registration in Terraform

**Context:** Terraform manages DNS records. AWS CLI changed the registered domain nameservers.

**Decision:** Terraform manages the AWS registered-domain resource and its Cloudflare nameservers.

**Rejected:** Use AWS CLI for nameserver updates.

**Why:** Terraform can detect nameserver drift and keep the registration config with the DNS records.

**Revisit when:** The domain registration moves away from AWS or DNS hosting moves away from Cloudflare.

**Links:** `terraform/global/route53.tf`.

## 2026-09-23: Move bc4.uk authoritative DNS to Cloudflare

**Context:** Route 53 hosted the zone. Cloudflare now serves the same DNS records. AWS sold the domain through its registrar associate, Gandi.

**Decision:** Cloudflare serves authoritative DNS for bc4.uk. Terraform manages DNS records. AWS Route 53 remains the registration service.

**Rejected:** Keep Route 53 as authoritative DNS.

**Why:** One DNS provider manages the DNS records. AWS can retain registration while Cloudflare hosts DNS.

**Revisit when:** Cloudflare DNS fails an operational or security requirement.

**Links:** `terraform/global/cloudflare.tf`, `terraform/global/route53.tf`.

## 2026-09-23: Use router DHCP on eth0

**Context:** The Pi moved to a network where the router supplies DHCP.

**Decision:** Netplan configures `eth0` for DHCP. Pyinfra purges `dnsmasq`. The BNS role stays inactive while the Pi uses a dynamic lease.

**Rejected:** Static IPv4 settings on the Pi and `dnsmasq` as the LAN DHCP server.

**Why:** The router supplies DHCP. The Pi's lease can change. BNS needs a stable LAN address.

**Revisit when:** The router reserves a stable address for the Pi and BNS must serve LAN clients.

**Links:** `pyinfra/tasks/network.py`, `pyinfra/tasks/remove_dnsmasq.py`, `pyinfra/inventory.py`.
