variable "dbt_config_path" {
  description = "Path to the dbt configuration YAML file"
  type        = string
  default     = "./dbt-config.yml"
}

variable "dbt_account_id" {
  description = "dbt Cloud account ID"
  type        = string
  sensitive   = true
}

variable "dbt_api_token" {
  description = "dbt Cloud API token"
  type        = string
  sensitive   = true
}

variable "token_map" {
  description = "Map of database credentials (warehouse tokens, API keys, etc.)"
  type        = map(string)
  sensitive   = true
  default     = {}
}

variable "target_name" {
  description = "Override the default target name from dbt_project.yml"
  type        = string
  default     = ""
}
