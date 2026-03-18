"""Unit tests for element ID extraction and flattening."""

from importer.element_ids import apply_element_ids


def test_apply_element_ids_emits_nested_project_connection() -> None:
    payload = {
        "account_id": 123,
        "account_name": "Test Account",
        "projects": [
            {
                "id": 165291,
                "name": "Audit Work",
                "key": "audit_work",
                "metadata": {
                    "connection_id": 90385,
                    "connection": {
                        "id": 90385,
                        "name": "Snowflake",
                        "type": "snowflake",
                    },
                },
                "environments": [],
                "profiles": [
                    {
                        "id": 111391,
                        "key": "prod",
                        "connection_id": 90385,
                        "connection_key": "connection_90385",
                        "credentials_id": 167239,
                    }
                ],
            }
        ],
        "globals": {
            "connections": {},
        },
    }

    records = apply_element_ids(payload)

    connection_rows = [
        row
        for row in records
        if row.get("element_type_code") == "CON" and row.get("dbt_id") == 90385
    ]

    assert len(connection_rows) == 1
    assert connection_rows[0]["key"] == "connection_90385"
    assert connection_rows[0]["resource_group"] == "Connections"


def test_apply_element_ids_dedupes_project_and_global_connection() -> None:
    payload = {
        "account_id": 123,
        "account_name": "Test Account",
        "projects": [
            {
                "id": 165291,
                "name": "Audit Work",
                "key": "audit_work",
                "metadata": {
                    "connection_id": 90385,
                    "connection": {
                        "id": 90385,
                        "name": "Snowflake",
                        "type": "snowflake",
                    },
                },
                "environments": [],
                "profiles": [],
            }
        ],
        "globals": {
            "connections": {
                "connection_90385": {
                    "id": 90385,
                    "key": "connection_90385",
                    "name": "Snowflake",
                    "type": "snowflake",
                }
            },
        },
    }

    records = apply_element_ids(payload)

    connection_rows = [
        row
        for row in records
        if row.get("element_type_code") == "CON" and row.get("dbt_id") == 90385
    ]

    assert len(connection_rows) == 1
