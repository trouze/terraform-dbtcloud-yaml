terraform {
  required_providers {
    dbtcloud = {
      source = "dbt-labs/dbtcloud"
    }
    null = {
      source = "hashicorp/null"
    }
  }
}

variable "account" {
  description = "Account-level metadata"
  type = object({
    name     = string
    host_url = string
    id       = optional(number)
  })
}

variable "globals" {
  description = "Global resources (connections, repositories, service tokens, groups, notifications, PrivateLink endpoints)"
  type = object({
    connections           = optional(list(any), [])
    repositories          = optional(list(any), [])
    service_tokens        = optional(list(any), [])
    groups                = optional(list(any), [])
    notifications         = optional(list(any), [])
    privatelink_endpoints = optional(list(any), [])
  })
  default = {
    connections           = []
    repositories          = []
    service_tokens        = []
    groups                = []
    notifications         = []
    privatelink_endpoints = []
  }
}

variable "projects" {
  description = "List of projects to create"
  type = list(object({
    key                   = string
    name                  = string
    repository            = any # Can be string (key) or object (inline)
    environments          = list(any)
    jobs                  = optional(list(any), [])
    environment_variables = optional(list(any), [])
    notifications         = optional(list(any), [])
  }))
}

variable "token_map" {
  description = "Map of credential token names to their actual values"
  type        = map(string)
  default     = {}
  sensitive   = true
}

variable "dbt_account_id" {
  description = "dbt Cloud account ID"
  type        = number
}

