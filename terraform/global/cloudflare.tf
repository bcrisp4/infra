locals {
  cloudflare_zones = {
    thecrisp_io    = "c6e4c52a7df970cb307f6a4164eff2f4"
    bencrisp_co_uk = "662c81f35160fc2fb078ce3e8810a48e"
  }
}

# thecrisp.io ----------------------------------------------------------------

resource "cloudflare_dns_record" "thecrisp_dkim_apple_sig1" {
  zone_id = local.cloudflare_zones.thecrisp_io
  name    = "sig1._domainkey.thecrisp.io"
  type    = "CNAME"
  content = "sig1.dkim.thecrisp.io.at.icloudmailadmin.com"
  proxied = false
  tags    = []
  ttl     = 3600
  settings = {
    flatten_cname = false
  }
}

resource "cloudflare_dns_record" "thecrisp_mx_mx01" {
  zone_id  = local.cloudflare_zones.thecrisp_io
  name     = "thecrisp.io"
  type     = "MX"
  content  = "mx01.mail.icloud.com"
  priority = 10
  proxied  = false
  tags     = []
  ttl      = 3600
  settings = {}
}

resource "cloudflare_dns_record" "thecrisp_mx_mx02" {
  zone_id  = local.cloudflare_zones.thecrisp_io
  name     = "thecrisp.io"
  type     = "MX"
  content  = "mx02.mail.icloud.com"
  priority = 10
  proxied  = false
  tags     = []
  ttl      = 3600
  settings = {}
}

resource "cloudflare_dns_record" "thecrisp_dmarc" {
  zone_id  = local.cloudflare_zones.thecrisp_io
  name     = "_dmarc.thecrisp.io"
  type     = "TXT"
  content  = jsonencode("v=DMARC1; p=none; rua=mailto:admin@thecrisp.io")
  proxied  = false
  tags     = []
  ttl      = 1
  settings = {}
}

resource "cloudflare_dns_record" "thecrisp_dkim_google" {
  zone_id  = local.cloudflare_zones.thecrisp_io
  name     = "google._domainkey.thecrisp.io"
  type     = "TXT"
  content  = "${jsonencode("v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnN3n+zTpwxa4txUNrjR2rrqhQ5tw3g9xfiyx5yZpqXHzN31o5LM+N/A5Z9SFr9VI1fXRt3NnK7THS3ETMBJXUUtUtJ3sSbjGKJzGBvIas2qacCmhV/iPzmwug5XOYt5zLXktgHa2bGkVd6EoB1HrqhRc4JLhAE/z73bCVc73yQppdNuaMsXUrCtN9onrdxU0X")} ${jsonencode("RELpin3GDofZBfDo0d0G8eRVDjofSFY6Ra4KlTYQo+8mZG022X1A9bApFfcXglV3c6pYpz4aDtO/859i1rKT37RqVKB8bPzApXhWO4Lyvx1em6iUy00MRcwiP9sKLYuHy2tQIpaovAYgTAjNHlsvQIDAQAB")}"
  proxied  = false
  tags     = []
  ttl      = 1
  settings = {}
}

resource "cloudflare_dns_record" "thecrisp_spf" {
  zone_id  = local.cloudflare_zones.thecrisp_io
  name     = "thecrisp.io"
  type     = "TXT"
  content  = jsonencode("v=spf1 include:_spf.google.com include:icloud.com ~all")
  proxied  = false
  tags     = []
  ttl      = 3600
  settings = {}
}

resource "cloudflare_dns_record" "thecrisp_apple_domain_verify" {
  zone_id  = local.cloudflare_zones.thecrisp_io
  name     = "thecrisp.io"
  type     = "TXT"
  content  = jsonencode("apple-domain=a1KmrFYvxYezdOeI")
  proxied  = false
  tags     = []
  ttl      = 3600
  settings = {}
}

resource "cloudflare_dns_record" "thecrisp_google_site_verify" {
  zone_id  = local.cloudflare_zones.thecrisp_io
  name     = "thecrisp.io"
  type     = "TXT"
  content  = jsonencode("google-site-verification=TW3-CW9xfcZkYBfyqHt-gTZfY_UcjxnaA4OMnppudww")
  proxied  = false
  tags     = []
  ttl      = 1
  settings = {}
}

# bencrisp.co.uk -------------------------------------------------------------

resource "cloudflare_dns_record" "bencrisp_dkim_apple_sig1" {
  zone_id = local.cloudflare_zones.bencrisp_co_uk
  name    = "sig1._domainkey.bencrisp.co.uk"
  type    = "CNAME"
  content = "sig1.dkim.bencrisp.co.uk.at.icloudmailadmin.com"
  proxied = false
  tags    = []
  ttl     = 3600
  settings = {
    flatten_cname = false
  }
}

resource "cloudflare_dns_record" "bencrisp_mx_mx01" {
  zone_id  = local.cloudflare_zones.bencrisp_co_uk
  name     = "bencrisp.co.uk"
  type     = "MX"
  content  = "mx01.mail.icloud.com"
  priority = 10
  proxied  = false
  tags     = []
  ttl      = 3600
  settings = {}
}

resource "cloudflare_dns_record" "bencrisp_mx_mx02" {
  zone_id  = local.cloudflare_zones.bencrisp_co_uk
  name     = "bencrisp.co.uk"
  type     = "MX"
  content  = "mx02.mail.icloud.com"
  priority = 10
  proxied  = false
  tags     = []
  ttl      = 3600
  settings = {}
}

resource "cloudflare_dns_record" "bencrisp_google_site_verify" {
  zone_id  = local.cloudflare_zones.bencrisp_co_uk
  name     = "bencrisp.co.uk"
  type     = "TXT"
  content  = jsonencode("google-site-verification=0Ig2y0KxuJDdtNr0HSLOw2dLgTiL1Nwsu_fh-dpcf2g")
  proxied  = false
  tags     = []
  ttl      = 1
  settings = {}
}

resource "cloudflare_dns_record" "bencrisp_apple_domain_verify" {
  zone_id  = local.cloudflare_zones.bencrisp_co_uk
  name     = "bencrisp.co.uk"
  type     = "TXT"
  content  = jsonencode("apple-domain=hdwg9eMvsdzjuahV")
  proxied  = false
  tags     = []
  ttl      = 3600
  settings = {}
}

resource "cloudflare_dns_record" "bencrisp_spf" {
  zone_id  = local.cloudflare_zones.bencrisp_co_uk
  name     = "bencrisp.co.uk"
  type     = "TXT"
  content  = jsonencode("v=spf1 include:_spf.google.com include:icloud.com ~all")
  proxied  = false
  tags     = []
  ttl      = 3600
  settings = {}
}

resource "cloudflare_dns_record" "bencrisp_dmarc" {
  zone_id  = local.cloudflare_zones.bencrisp_co_uk
  name     = "_dmarc.bencrisp.co.uk"
  type     = "TXT"
  content  = jsonencode("v=DMARC1; p=none; rua=mailto:admin@bencrisp.co.uk")
  proxied  = false
  tags     = []
  ttl      = 1
  settings = {}
}

resource "cloudflare_dns_record" "bencrisp_dkim_google" {
  zone_id  = local.cloudflare_zones.bencrisp_co_uk
  name     = "google._domainkey.bencrisp.co.uk"
  type     = "TXT"
  content  = "${jsonencode("v=DKIM1; k=rsa; p=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAp+efUItklStDC4POf3p5IlMQQLdSoBvnRzpdLdZ96GHnF/smPIsvMJjVSu+jW9kAxs0GyiY9rG/mTLiSy9Lz+lTrCX1t4frdaoDn4dedt0SluYRf4vNFe90/oTcf7FDuXnVd9/KYyHk6NM+qByiVimyovjWtpj+jue+RDjXxj+VbmPGRm2YzK0r1wGn7pTEpa")} ${jsonencode("x1yVqbvKalZuuLxjycTRoeQdP6JdzE0hFU6WTPQeBrfE6e//1AlIagczxQFWfeech01C8BGaJSh/GhfYie3UcNY1COIq09kZVzhrRvpsVZ3pnhkkNg2x40+qZKOjxlhEXS/L9bprWXJY7Txp9V0yQIDAQAB")}"
  proxied  = false
  tags     = []
  ttl      = 1
  settings = {}
}

