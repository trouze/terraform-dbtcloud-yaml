# Invalid moved block for error testing
# Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.3

# Invalid: Missing 'to' field
moved {
  from = module.dbt_cloud.dbtcloud_project.projects["test"]
}

# Invalid: Missing 'from' field
moved {
  to = module.dbt_cloud.dbtcloud_project.protected_projects["test"]
}
