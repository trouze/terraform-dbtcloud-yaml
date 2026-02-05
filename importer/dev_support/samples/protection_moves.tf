# Generated moved blocks for protection status changes
# These tell Terraform to move existing resources between protected/unprotected blocks
# without destroying and recreating them

# Move sse_dm_fin_fido resources from unprotected to protected
# Move repository from unprotected to protected
moved {
  from = module.dbt_cloud.module.projects_v2[0].dbtcloud_repository.repositories["sse_dm_fin_fido"]
  to   = module.dbt_cloud.module.projects_v2[0].dbtcloud_repository.protected_repositories["sse_dm_fin_fido"]
}
