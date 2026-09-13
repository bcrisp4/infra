resource "aws_route53_zone" "bc4_uk" {
  name          = "bc4.uk"
  comment       = "HostedZone created by Route53 Registrar"
  force_destroy = false
}

resource "aws_route53_record" "bc4_uk_mx" {
  zone_id = aws_route53_zone.bc4_uk.zone_id
  name    = "bc4.uk"
  type    = "MX"
  ttl     = 600
  records = [
    "10 mx01.mail.icloud.com.",
    "10 mx02.mail.icloud.com.",
  ]
}

resource "aws_route53_record" "bc4_uk_txt" {
  zone_id = aws_route53_zone.bc4_uk.zone_id
  name    = "bc4.uk"
  type    = "TXT"
  ttl     = 60
  records = [
    "apple-domain=eeNAiCD2GYjrhtAR",
    "v=spf1 include:icloud.com ~all",
  ]
}

resource "aws_route53_record" "bc4_uk_dkim" {
  zone_id = aws_route53_zone.bc4_uk.zone_id
  name    = "sig1._domainkey.bc4.uk"
  type    = "CNAME"
  ttl     = 600
  records = ["sig1.dkim.bc4.uk.at.icloudmailadmin.com."]
}

resource "aws_route53_record" "bc4_uk_dmarc" {
  zone_id = aws_route53_zone.bc4_uk.zone_id
  name    = "_dmarc.bc4.uk"
  type    = "TXT"
  ttl     = 60
  records = ["v=DMARC1;p=quarantine;pct=100;fo=1"]
}
