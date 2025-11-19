# dbt Cloud Account Migration Importer Plan

## Context

- Goal: build an importer that reads an existing dbt Cloud account (via API), emits a YAML file compatible with `schemas/v1.json`, and applies it to a target account using the existing Terraform module + provider data sources.
- Dependencies: dbt Cloud APIs (`dev_support/api_reference/dbt_api_v2 with references.yaml`), Terraform provider resources/data sources (`/Users/operator/Documents/git/dbt-labs/terraform-provider-dbtcloud/docs/`), current YAML schema (`schemas/v1.json`).

## Phase 0 – Schema Baseline

1. **Review `schemas/v1.json` + `docs/configuration/yaml-schema.md`**  
   - Confirm every field the importer needs is already representable.  
   - Identify schema gaps (e.g., catalog under credential, job deferral by name, notifications) and decide whether to cut scope or introduce a `schemas/v2.json`.
2. **Decision checkpoint**  
   - If new fields are required, draft v2 schema requirements before building the importer to avoid rework.

## Phase 1 – Source Account Analysis

1. Enumerate API endpoints needed to gather all project assets (projects, repositories, credentials, environments, jobs, env vars, notifications, service tokens, groups, connections, PrivateLink endpoints, semantic layer configs).  
2. Prototype API calls (curl/httpie) to validate pagination + filtering; document required auth scopes.  
3. Define an internal data model that captures everything we need from the source account independent of Terraform.

## Phase 2 – YAML Normalization

1. Map the internal model to the YAML schema (v1 or v2).  
2. Implement logic to strip source-only IDs (project/job/env IDs) while preserving references that must match across objects (environment names, token keys).  
3. Provide a mechanism (e.g., metadata or comments) to flag fields requiring manual mapping in the target account (connection IDs, OAuth configs, etc.).

## Phase 3 – Target Account Preparation

1. Catalog required Terraform data sources for lookups (connections, repositories, groups, service tokens).  
2. Define how importer output records placeholders (e.g., `connection_id: LOOKUP:global_connection.my_connection`).  
3. Update documentation to instruct operators on running `terraform apply` with the generated YAML + necessary var files/token maps.

## Phase 4 – Implementation

1. Build the extractor CLI/script (language TBD) with modular steps: fetch → normalize → emit YAML.  
2. Include retries/backoff and pagination handling.  
3. Provide unit tests for serialization + integration smoke test against a sandbox account.

## Phase 5 – Testing & Validation

1. Dry-run importer against a non-production account; verify YAML passes `yamllint` + `yamlls` schema validation.  
2. Run Terraform against a clean target workspace to ensure all resources are created and state is consistent.  
3. Iterate on edge cases (empty jobs, archived resources, disabled integrations).

## Deliverables

- Updated `schemas/v1.json` or new `schemas/v2.json` (if required).  
- Importer tool + documentation (usage, prerequisites, troubleshooting).  
- Sample YAML outputs and Terraform instruction guide for migrations.  
- Backlog of stretch goals (notifications/lineage integrations, semantic layer configs, etc.).
