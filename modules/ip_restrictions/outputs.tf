output "ip_rule_ids" {
  description = "Map of IP rule key to dbt Cloud IP restriction rule ID"
  value       = { for k, r in dbtcloud_ip_restrictions_rule.ip_rules : k => r.id }
}
