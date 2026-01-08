#############################################
# Data Sources for LOOKUP Placeholder Resolution
# 
# Resolves LOOKUP: placeholders by querying existing resources in the target account.
# Users must create these resources manually before running Terraform.
#############################################

# Resolve LOOKUP connections by name
# Use global_connections data source and filter by name
data "dbtcloud_global_connections" "all" {}

locals {
  # Map LOOKUP connections to their IDs by filtering global_connections
  lookup_connection_ids = {
    for lookup_key in local.lookup_connections :
    lookup_key => try([
      for conn in data.dbtcloud_global_connections.all.connections :
      conn.id if conn.name == replace(lookup_key, "LOOKUP:", "")
    ][0], null)
  }
}

# Resolve LOOKUP repositories by name (if needed)
# Note: Repositories are project-scoped, so this may need project_id
# For now, we'll handle repository lookups differently in projects.tf

#############################################
# Git Integration Discovery
# 
# Retrieves target account's Git integration IDs (GitHub, GitLab, ADO).
# These IDs are account-specific and cannot be migrated from source account.
# Requires PAT (Personal Access Token) - service tokens cannot access integrations API.
#############################################

# Retrieve GitHub App installations from target account
# NOTE: Requires PAT token (dbtu_*), not service token
data "http" "github_installations" {
  count = var.dbt_pat != null ? 1 : 0

  url = format("%s/api/v2/integrations/github/installations/", local.dbt_host_url)
  request_headers = {
    Authorization = format("Bearer %s", var.dbt_pat)
  }
}

locals {
  # Determine host URL - use provided dbt_host_url or fallback to account.host_url
  dbt_host_url = coalesce(var.dbt_host_url, var.account.host_url, "https://cloud.getdbt.com")

  # Parse GitHub installations response
  # Response is an array of installation objects: [{"id": 267820, "access_tokens_url": "..."}, ...]
  github_installations_raw = var.dbt_pat != null && length(data.http.github_installations) > 0 ? (
    try(jsondecode(data.http.github_installations[0].response_body), [])
  ) : []

  # Get primary GitHub installation ID (first one, typically there's only one per account)
  # Filter to only GitHub installations (access_tokens_url contains "github")
  github_installations = [
    for inst in local.github_installations_raw :
    inst if can(regex("github", try(inst.access_tokens_url, "")))
  ]

  github_installation_id = length(local.github_installations) > 0 ? local.github_installations[0].id : null
}

