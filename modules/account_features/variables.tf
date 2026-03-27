variable "features" {
  description = "Account feature flags from YAML account_features. Set to null to skip (no resource created)."
  type        = any
  default     = null
}
