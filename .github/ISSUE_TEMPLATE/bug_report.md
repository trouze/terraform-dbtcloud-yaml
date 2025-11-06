name: Bug Report
description: Report a bug to help us improve
labels: ["bug"]

body:
  - type: markdown
    attributes:
      value: |
        Thank you for reporting a bug! Please provide as much detail as possible to help us resolve it.

  - type: textarea
    id: description
    attributes:
      label: Description
      description: Clear and concise description of the bug
      placeholder: |
        What happened?
        What did you expect to happen?
    validations:
      required: true

  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
      description: Steps to reproduce the bug
      placeholder: |
        1. Configure YAML with...
        2. Run terraform plan
        3. See error...
    validations:
      required: true

  - type: textarea
    id: yaml-config
    attributes:
      label: YAML Configuration
      description: Relevant portion of your YAML config (remove sensitive data)
      render: yaml
      placeholder: |
        project:
          name: example
          # ...

  - type: textarea
    id: terraform-config
    attributes:
      label: Terraform Configuration
      description: Relevant portion of your Terraform config (remove sensitive data)
      render: hcl
      placeholder: |
        module "dbt_cloud" {
          # ...
        }

  - type: textarea
    id: error
    attributes:
      label: Error Output
      description: Full error message or logs
      render: shell

  - type: textarea
    id: environment
    attributes:
      label: Environment
      description: |
        - Terraform version (terraform --version)
        - dbt Cloud provider version
        - Operating system
        - dbt Cloud account type (Single tenant, multi-tenant, etc.)
      placeholder: |
        - Terraform v1.5.0
        - dbtcloud provider v0.3.0
        - macOS 13.5
        - dbt Cloud (multi-tenant)

  - type: checkboxes
    id: checklist
    attributes:
      label: Checklist
      options:
        - label: I've searched for existing issues
          required: true
        - label: I've provided a clear description
          required: true
        - label: I've included steps to reproduce
          required: true
