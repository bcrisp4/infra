"""dns_servers role: bns caching DNS forwarder + adblock.

Machine-specific bind address (bns_listen_address) lives in the host dict in
inventory.py. Upstream + blocklist policy is role-wide and lives here.
"""

bns_enabled = True

bns_upstreams = [
    {
        "type": "doh",
        "url": "https://cloudflare-dns.com/dns-query",
        "endpoint_ips": ["1.1.1.1", "1.0.0.1"],
        "timeout": "5s",
    },
    {
        "type": "doh",
        "url": "https://dns.quad9.net/dns-query",
        "endpoint_ips": ["9.9.9.9", "149.112.112.112"],
        "timeout": "5s",
    },
]

# hagezi pro = balanced general blocklist; tif = threat intelligence feeds
# (malware, phishing, scam domains).
bns_blocklists = [
    {
        "name": "hagezi-pro",
        "url": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/pro.txt",
    },
    {
        "name": "hagezi-tif",
        "url": "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/tif.txt",
    },
]
