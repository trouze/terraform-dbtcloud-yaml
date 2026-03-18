from importer.fetcher import _merge_project_connections_into_globals
from importer.models import Connection


def test_merge_project_connections_into_globals_promotes_nested_project_connections() -> None:
    existing = {
        "snowflake_sandbox_ska67070": Connection(
            key="snowflake_sandbox_ska67070",
            id=51284,
            name="Snowflake Sandbox",
            type="snowflake",
        ),
    }
    project_items = [
        {
            "id": 89617,
            "name": "Benoit Sandbox",
            "connection_id": 106827,
            "connection_key": "connection_106827",
            "connection": {
                "id": 106827,
                "name": "Project-scoped Snowflake",
                "type": "snowflake",
            },
        },
        {
            "id": 90001,
            "name": "Carol Sandbox",
            "metadata": {
                "connection_id": 74563,
                "connection_key": "connection_74563",
                "connection": {
                    "id": 74563,
                    "name": "Project metadata connection",
                    "type": "snowflake",
                },
            },
        },
    ]

    merged = _merge_project_connections_into_globals(project_items, existing)
    merged_keys = set(merged.keys())

    assert "snowflake_sandbox_ska67070" in merged_keys
    assert "connection_106827" in merged_keys
    assert "connection_74563" in merged_keys


def test_merge_project_connections_into_globals_dedupes_existing_connections() -> None:
    existing = {
        "connection_106827": Connection(
            key="connection_106827",
            id=106827,
            name="Existing",
            type="snowflake",
        ),
    }
    project_items = [
        {
            "id": 89617,
            "connection_id": 106827,
            "connection_key": "connection_106827",
            "connection": {
                "id": 106827,
                "name": "Duplicate",
                "type": "snowflake",
            },
        },
    ]

    merged = _merge_project_connections_into_globals(project_items, existing)

    assert len(merged) == 1
    assert merged["connection_106827"].key == "connection_106827"
