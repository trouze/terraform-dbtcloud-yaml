# Auto-generated: Move resources between protected/unprotected resource blocks
# Generated: 2026-02-04
#
# These moved blocks handle protection status changes.
# After `terraform apply` succeeds, you can delete this file.

# Project "sse_dm_fin_fido" is now unprotected
moved {
  from = module.dbt_cloud.module.projects_v2[0].dbtcloud_project.protected_projects["sse_dm_fin_fido"]
  to   = module.dbt_cloud.module.projects_v2[0].dbtcloud_project.projects["sse_dm_fin_fido"]
}
