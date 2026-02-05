# Valid Terraform provider configuration for testing
# Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.3

terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
  
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = ">= 0.2"
    }
  }
}

provider "dbtcloud" {
  # Configuration from environment variables:
  # - DBT_CLOUD_ACCOUNT_ID
  # - DBT_CLOUD_TOKEN
}
