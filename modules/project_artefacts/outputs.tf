output "project_artefact_ids" {
  description = "Map of project key to project_artefacts resource ID"
  value       = { for k, a in dbtcloud_project_artefacts.artefacts : k => a.id }
}
