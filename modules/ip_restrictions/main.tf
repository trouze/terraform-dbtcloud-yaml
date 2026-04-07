terraform {
  required_version = ">= 1.7"
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = "~> 1.8"
    }
  }
}

#############################################
# IP Restrictions Rules (account-level collection)
#############################################

locals {
  # COMPAT(v1-schema): for_each key from key or legacy name — align with v2 schema when canonical.
  ip_rules_map = {
    for rule in var.ip_rules_data :
    try(rule.key, rule.name) => rule
  }

  unprotected_ip_restrictions_map = {
    for key, rule in local.ip_rules_map :
    key => rule if !try(rule.protected, false)
  }

  protected_ip_restrictions_map = {
    for key, rule in local.ip_rules_map :
    key => rule if try(rule.protected, false)
  }

  # Provider-agnostic provenance (v2 used resource_metadata on the resource; stock
  # dbtcloud often does not expose it on this type). Exposed via output for CI / audits.
  ip_rules_provenance = {
    for key, rule in local.ip_rules_map :
    key => {
      source_key      = key
      source_name     = rule.name
      source_identity = "IPRST:${key}"
      source_id       = try(rule.id, null)
      protected       = try(rule.protected, false)
    }
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

  lifecycle {
    prevent_destroy = true
  }
}
