# Main Terraform configuration for testing
# Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.3

variable "test_mode" {
  description = "Whether running in test mode"
  type        = bool
  default     = true
}

variable "account_id" {
  description = "dbt Cloud account ID"
  type        = number
  default     = 12345
}

# Module placeholder for testing moved blocks
# Note: In real tests, the module would be defined elsewhere
# This is a minimal setup to validate HCL syntax

locals {
  project_keys = ["test_project"]
}
