variable "dbt_account_id" {
  type        = number
  description = "dbt Cloud Account ID"
}

variable "dbt_token" {
  type        = string
  description = "dbt Cloud API Token"
  default     = "test-token-not-real"
  sensitive   = true
}

variable "dbt_host_url" {
  type        = string
  description = "dbt Cloud URL"
  default     = "https://cloud.getdbt.com"
}

variable "target_name" {
  type        = string
  description = "dbt target name"
  default     = "dev"
}

variable "token_map" {
  type        = map(string)
  description = "Map of token names to warehouse tokens"
  default = {
    "dev_token"  = "test-token-dev"
    "prod_token" = "test-token-prod"
  }
  sensitive = true
}
