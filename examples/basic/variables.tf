variable "dbt_account_id" {
  description = "dbt Cloud account ID"
  type        = number
  sensitive   = true
}

variable "dbt_token" {
  description = "dbt Cloud API token"
  type        = string
  sensitive   = true
}

variable "dbt_pat" {
  type = string
  sensitive = true
  default = ""
}

variable "dbt_host_url" {
  description = "dbt Cloud host URL"
  type        = string
  default     = "https://cloud.getdbt.com"
}

variable "token_map" {
  description = "Map of credential token names to values"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "target_name" {
  description = "Default target name"
  type        = string
  default     = "prod"
}
