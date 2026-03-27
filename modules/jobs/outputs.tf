output "job_ids" {
  description = "Map of composite key (project_key_job_key) to dbt Cloud job ID"
  value = merge(
    { for k, j in dbtcloud_job.jobs : k => j.id },
    { for k, j in dbtcloud_job.protected_jobs : k => j.id }
  )
}
