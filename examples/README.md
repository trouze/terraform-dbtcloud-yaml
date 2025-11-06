# dbt Cloud Module Usage Examples

This directory contains examples of how to use the dbt Cloud Terraform module in different scenarios.

## Basic Example

The `basic/` example shows the minimal setup needed to use the module:

```hcl
module "dbt_cloud" {
  source = "git::https://github.com/yourusername/dbt-terraform-modules-yaml.git"
  
  yaml_file        = file("${path.module}/dbt-config.yml")
  dbt_account_id   = var.dbt_account_id
  dbt_token        = var.dbt_token
  dbt_host_url     = var.dbt_host_url
  token_map        = var.token_map
  target_name      = "prod"
}
```

## Available Examples

- **basic/** - Minimal setup with a single environment
- **advanced/** - Multi-environment setup with complex job configurations

## Running the Examples

1. Copy the example directory to your workspace
2. Create a `terraform.tfvars` file with your dbt Cloud credentials
3. Run `terraform init` to initialize the working directory
4. Run `terraform plan` to preview changes
5. Run `terraform apply` to deploy

## Variables

All examples use these required variables:

- `dbt_account_id` - Your dbt Cloud account ID
- `dbt_token` - Your dbt Cloud API token
- `dbt_host_url` - Your dbt Cloud host URL
- `yaml_file` - Path to your YAML configuration

Optional variables:
- `token_map` - Map of credential tokens
- `target_name` - Default target name

## See Also

- [Main README](../README.md) - Full documentation
- [YAML Configuration Spec](../README.md#yaml-configuration-spec) - Configuration options
