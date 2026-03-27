terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
  }
}

locals {
  ip_rules_map = {
    for rule in var.ip_rules_data :
    try(rule.key, rule.name) => rule
  }
}

resource "dbtcloud_ip_restrictions_rule" "ip_rules" {
  for_each = local.ip_rules_map

  name             = each.value.name
  type             = try(each.value.type, "allow")
  description      = try(each.value.description, null)
  rule_set_enabled = try(each.value.rule_set_enabled, true)
  cidrs = [
    for c in try(each.value.cidrs, []) : { cidr = c.cidr }
  ]
}
