"""Schema validation tests for dbt Cloud YAML configurations."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATHS = {
    "v1": REPO_ROOT / "schemas" / "v1.json",
    "v2": REPO_ROOT / "schemas" / "v2.json",
}


class SchemaValidationTest(unittest.TestCase):
    """Validate representative YAML files against the JSON Schemas."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.validators = {
            version: Draft202012Validator(json.loads(path.read_text()))
            for version, path in SCHEMA_PATHS.items()
        }

    def assert_schema_valid(self, yaml_relative_path: str, schema_version: str) -> None:
        yaml_path = REPO_ROOT / yaml_relative_path
        self.assertTrue(yaml_path.exists(), f"Fixture not found: {yaml_path}")

        with yaml_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)

        validator = self.validators[schema_version]
        errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))

        if errors:
            formatted = "\n".join(
                f"- {yaml_relative_path}::{'.'.join(str(p) for p in err.path)} -> {err.message}"
                for err in errors
            )
            self.fail(f"Schema validation failed for {yaml_relative_path} against {schema_version}:\n{formatted}")

    def test_fixtures_basic_v1_schema(self) -> None:
        """Validate the basic Terraform fixture against v1 schema."""
        self.assert_schema_valid("test/fixtures/basic/dbt-config.yml", "v1")

    def test_fixtures_complete_v1_schema(self) -> None:
        """Validate the comprehensive fixture against v1 schema."""
        self.assert_schema_valid("test/fixtures/complete/dbt-config.yml", "v1")

    def test_v2_full_fixture(self) -> None:
        """Validate the importer-oriented v2 fixture against v2 schema."""
        self.assert_schema_valid("test/fixtures/v2_full/dbt-config.yml", "v2")


if __name__ == "__main__":
    unittest.main()

