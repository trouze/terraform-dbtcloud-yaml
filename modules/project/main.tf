terraform {
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
    }
  }
}

resource "dbtcloud_project" "project" {
  name = "${var.target_name}${var.project_name}"
}
