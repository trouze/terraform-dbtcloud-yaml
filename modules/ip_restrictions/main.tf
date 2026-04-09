terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.9"
    }
  }
}

#############################################
# IP Restrictions Rules (account-level collection)
#############################################

locals {
  ip_rules_map = {
    for rule in var.ip_rules_data :
    rule.key => rule
  }

  unprotected_ip_restrictions_map = {
    for key, rule in local.ip_rules_map :
    key => rule if !try(rule.protected, false)
  }

  protected_ip_restrictions_map = {
    for key, rule in local.ip_rules_map :
    key => rule if try(rule.protected, false)
  }
}

resource "dbtcloud_ip_restrictions_rule" "ip_rules" {
  for_each = local.unprotected_ip_restrictions_map

  name             = each.value.name
  type             = try(each.value.type, "allow")
  description      = try(each.value.description, null)
  rule_set_enabled = try(each.value.rule_set_enabled, false)

  cidrs = [
    for c in try(each.value.cidrs, []) : {
      cidr = c.cidr
    }
  ]

  # resource_metadata: pending official dbtcloud provider support (see importer projects_v2/ip_restrictions.tf).
  # resource_metadata = {
  #   source_id       = try(each.value.id, null)
  #   source_identity = "IPRST:${each.key}"
  #   source_key      = each.key
  #   source_name     = each.value.name
  # }
}

resource "dbtcloud_ip_restrictions_rule" "protected_ip_rules" {
  for_each = local.protected_ip_restrictions_map

  name             = each.value.name
  type             = try(each.value.type, "allow")
  description      = try(each.value.description, null)
  rule_set_enabled = try(each.value.rule_set_enabled, false)

  cidrs = [
    for c in try(each.value.cidrs, []) : {
      cidr = c.cidr
    }
  ]

  # resource_metadata: pending official dbtcloud provider support (see importer projects_v2/ip_restrictions.tf).
  # resource_metadata = {
  #   source_id       = try(each.value.id, null)
  #   source_identity = "IPRST:${each.key}"
  #   source_key      = each.key
  #   source_name     = each.value.name
  # }

  lifecycle {
    prevent_destroy = true
  }
}
