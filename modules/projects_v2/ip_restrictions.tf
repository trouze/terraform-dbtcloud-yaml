#############################################
# IP Restrictions Rules (account-level collection)
#############################################

locals {
  unprotected_ip_restrictions_map = {
    for key, rule in local.ip_restrictions_map :
    key => rule if !try(rule.protected, false)
  }
  protected_ip_restrictions_map = {
    for key, rule in local.ip_restrictions_map :
    key => rule if try(rule.protected, false)
  }
}

resource "dbtcloud_ip_restrictions_rule" "rules" {
  for_each = local.unprotected_ip_restrictions_map

  name             = each.value.name
  type             = try(each.value.type, "allow")
  description      = try(each.value.description, null)
  rule_set_enabled = try(each.value.rule_set_enabled, false)

  dynamic "cidrs" {
    for_each = try(each.value.cidrs, [])
    content {
      cidr        = cidrs.value.cidr
      cidr_ipv6   = try(cidrs.value.cidr_ipv6, null)
      description = try(cidrs.value.description, null)
    }
  }

  resource_metadata = {
    source_id       = try(each.value.id, null)
    source_identity = "IPRST:${each.key}"
    source_key      = each.key
    source_name     = each.value.name
  }
}

resource "dbtcloud_ip_restrictions_rule" "protected_rules" {
  for_each = local.protected_ip_restrictions_map

  name             = each.value.name
  type             = try(each.value.type, "allow")
  description      = try(each.value.description, null)
  rule_set_enabled = try(each.value.rule_set_enabled, false)

  dynamic "cidrs" {
    for_each = try(each.value.cidrs, [])
    content {
      cidr        = cidrs.value.cidr
      cidr_ipv6   = try(cidrs.value.cidr_ipv6, null)
      description = try(cidrs.value.description, null)
    }
  }

  resource_metadata = {
    source_id       = try(each.value.id, null)
    source_identity = "IPRST:${each.key}"
    source_key      = each.key
    source_name     = each.value.name
  }

  lifecycle {
    prevent_destroy = true
  }
}
