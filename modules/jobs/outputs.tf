output "job_ids" {
  value = { for key, job in dbtcloud_job.job : key => job.id }
}

// {"QA_CI_job": "1234"}
