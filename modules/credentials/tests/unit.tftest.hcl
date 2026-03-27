# Unit tests for modules/credentials
# Validates that the correct credential resource type is created for each
# warehouse adapter, and that Snowflake auth_type routing works correctly.
# Run from modules/credentials/: terraform test

mock_provider "dbtcloud" {}

# ── Databricks credentials ────────────────────────────────────────────────────

run "databricks_credential_created" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name       = "Prod"
            key        = "prod"
            credential = { credential_type = "databricks" }
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    environment_credentials = {
      analytics_prod = {
        credential_type = "databricks"
        token           = "dapi-fake-token"
        schema          = "analytics_prod"
      }
    }
  }

  assert {
    condition     = length(dbtcloud_databricks_credential.credentials) == 1
    error_message = "Expected one Databricks credential to be created"
  }

  assert {
    condition     = dbtcloud_databricks_credential.credentials["analytics_prod"].schema == "analytics_prod"
    error_message = "Databricks credential schema should match"
  }
}

# ── Snowflake credentials — password auth ─────────────────────────────────────

run "snowflake_password_credential_created" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name       = "Prod"
            key        = "prod"
            credential = { credential_type = "snowflake" }
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    environment_credentials = {
      analytics_prod = {
        credential_type = "snowflake"
        auth_type       = "password"
        user            = "dbt_user"
        password        = "secret"
        schema          = "analytics"
        num_threads     = 4
      }
    }
  }

  assert {
    condition     = length(dbtcloud_snowflake_credential.credentials_password) == 1
    error_message = "Expected one Snowflake password credential"
  }

  assert {
    condition     = length(dbtcloud_snowflake_credential.credentials_keypair) == 0
    error_message = "No keypair credential should be created for password auth"
  }
}

# ── Snowflake credentials — keypair auth ──────────────────────────────────────

run "snowflake_keypair_credential_created" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name       = "Prod"
            key        = "prod"
            credential = { credential_type = "snowflake" }
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    environment_credentials = {
      analytics_prod = {
        credential_type = "snowflake"
        auth_type       = "keypair"
        user            = "dbt_user"
        private_key     = "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----"
        schema          = "analytics"
        num_threads     = 4
      }
    }
  }

  assert {
    condition     = length(dbtcloud_snowflake_credential.credentials_keypair) == 1
    error_message = "Expected one Snowflake keypair credential"
  }

  assert {
    condition     = length(dbtcloud_snowflake_credential.credentials_password) == 0
    error_message = "No password credential should be created for keypair auth"
  }
}

# ── BigQuery credentials ──────────────────────────────────────────────────────

run "bigquery_credential_created" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name       = "Prod"
            key        = "prod"
            credential = { credential_type = "bigquery" }
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    environment_credentials = {
      analytics_prod = {
        credential_type = "bigquery"
        dataset         = "dbt_prod"
        num_threads     = 4
      }
    }
  }

  assert {
    condition     = length(dbtcloud_bigquery_credential.credentials) == 1
    error_message = "Expected one BigQuery credential"
  }
}

# ── Postgres credentials ──────────────────────────────────────────────────────

run "postgres_credential_created" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name       = "Prod"
            key        = "prod"
            credential = { credential_type = "postgres" }
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    environment_credentials = {
      analytics_prod = {
        credential_type = "postgres"
        username        = "dbt_user"
        password        = "secret"
        default_schema  = "dbt_prod"
      }
    }
  }

  assert {
    condition     = length(dbtcloud_postgres_credential.credentials) == 1
    error_message = "Expected one Postgres credential"
  }
}

# ── Fabric credentials — SQL vs service principal ─────────────────────────────

run "fabric_sql_credential_created_without_tenant_id" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name       = "Prod"
            key        = "prod"
            credential = { credential_type = "fabric" }
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    environment_credentials = {
      analytics_prod = {
        credential_type = "fabric"
        user            = "dbt_user"
        password        = "secret"
        schema          = "dbt_prod"
      }
    }
  }

  assert {
    condition     = length(dbtcloud_fabric_credential.credentials_sql) == 1
    error_message = "Expected Fabric SQL credential when no tenant_id"
  }

  assert {
    condition     = length(dbtcloud_fabric_credential.credentials_sp) == 0
    error_message = "No Fabric SP credential should be created without tenant_id"
  }
}

run "fabric_service_principal_credential_created_with_tenant_id" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name       = "Prod"
            key        = "prod"
            credential = { credential_type = "fabric" }
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    environment_credentials = {
      analytics_prod = {
        credential_type = "fabric"
        tenant_id       = "tenant-abc"
        client_id       = "client-abc"
        client_secret   = "secret"
        schema          = "dbt_prod"
      }
    }
  }

  assert {
    condition     = length(dbtcloud_fabric_credential.credentials_sp) == 1
    error_message = "Expected Fabric SP credential when tenant_id is present"
  }

  assert {
    condition     = length(dbtcloud_fabric_credential.credentials_sql) == 0
    error_message = "No Fabric SQL credential should be created with tenant_id"
  }
}

# ── Only one credential resource type created per entry ───────────────────────

run "only_matching_resource_type_created" {
  command = plan

  variables {
    projects = [
      {
        key  = "analytics"
        name = "Analytics"
        environments = [
          {
            name       = "Prod"
            key        = "prod"
            credential = { credential_type = "redshift" }
          }
        ]
      }
    ]
    project_ids = { analytics = "1001" }
    environment_credentials = {
      analytics_prod = {
        credential_type = "redshift"
        username        = "dbt_user"
        password        = "secret"
        default_schema  = "dbt_prod"
      }
    }
  }

  assert {
    condition     = length(dbtcloud_redshift_credential.credentials) == 1
    error_message = "Expected one Redshift credential"
  }

  assert {
    condition     = length(dbtcloud_databricks_credential.credentials) == 0
    error_message = "No Databricks credential should be created for redshift type"
  }

  assert {
    condition     = length(dbtcloud_snowflake_credential.credentials_password) == 0
    error_message = "No Snowflake credential should be created for redshift type"
  }

  assert {
    condition     = length(dbtcloud_bigquery_credential.credentials) == 0
    error_message = "No BigQuery credential should be created for redshift type"
  }
}
