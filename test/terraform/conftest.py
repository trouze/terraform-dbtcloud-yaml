"""Pytest configuration and fixtures for Terraform integration tests.

This module provides:
- Terraform-specific test fixtures
- Test environment setup utilities
- Mocked and real Terraform execution helpers

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.3
"""

import json
import os
import pytest
import shutil
from pathlib import Path
from typing import Generator, Dict, Any, Optional

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "e2e" / "helpers"))

from terraform_runner import TerraformRunner, TerraformResult, create_test_terraform_environment


# =============================================================================
# Configuration
# =============================================================================

# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture
def terraform_workspace(tmp_path: Path) -> Path:
    """Create an isolated Terraform workspace for testing.
    
    Returns:
        Path to the workspace directory
    """
    workspace = tmp_path / "terraform_test"
    workspace.mkdir(parents=True)
    return workspace


@pytest.fixture
def terraform_dir(terraform_workspace: Path) -> Path:
    """Create a terraform directory within the workspace.
    
    Returns:
        Path to the terraform directory
    """
    tf_dir = terraform_workspace / "terraform"
    tf_dir.mkdir(parents=True)
    return tf_dir


@pytest.fixture
def valid_config_dir() -> Path:
    """Path to valid Terraform configuration fixtures."""
    return FIXTURES_DIR / "valid_config"


@pytest.fixture
def invalid_config_dir() -> Path:
    """Path to invalid Terraform configuration fixtures."""
    return FIXTURES_DIR / "invalid_config"


# =============================================================================
# Terraform Runner Fixtures
# =============================================================================

@pytest.fixture
def terraform_runner(terraform_dir: Path) -> TerraformRunner:
    """Create a TerraformRunner instance for testing.
    
    Returns:
        Configured TerraformRunner
    """
    return TerraformRunner(
        working_dir=terraform_dir,
        mock_apply=True,
        mock_destroy=True,
    )


@pytest.fixture
def real_terraform_runner(terraform_dir: Path) -> TerraformRunner:
    """Create a TerraformRunner with real apply/destroy (use carefully).
    
    Returns:
        TerraformRunner with mocking disabled
    """
    return TerraformRunner(
        working_dir=terraform_dir,
        mock_apply=False,
        mock_destroy=False,
    )


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture
def minimal_providers_tf() -> str:
    """Minimal providers.tf content for testing."""
    return '''terraform {
  backend "local" {
    path = "terraform.tfstate"
  }
  
  required_providers {
    dbtcloud = {
      source  = "dbt-labs/dbtcloud"
      version = ">= 0.2"
    }
  }
}

provider "dbtcloud" {
  # Provider configuration from environment
}
'''


@pytest.fixture
def minimal_main_tf() -> str:
    """Minimal main.tf content for testing."""
    return '''# Test Terraform configuration
# Generated for testing purposes

variable "test_mode" {
  description = "Whether running in test mode"
  type        = bool
  default     = true
}
'''


@pytest.fixture
def protection_moves_tf() -> str:
    """Sample protection_moves.tf with moved blocks."""
    return '''# Protection moves generated for testing
# Reference: PRD 11.01 Section 1.3

moved {
  from = module.dbt_cloud.module.projects_v2[0].dbtcloud_project.projects["test_project"]
  to   = module.dbt_cloud.module.projects_v2[0].dbtcloud_project.protected_projects["test_project"]
}

moved {
  from = module.dbt_cloud.module.projects_v2[0].dbtcloud_repository.repositories["test_project"]
  to   = module.dbt_cloud.module.projects_v2[0].dbtcloud_repository.protected_repositories["test_project"]
}

moved {
  from = module.dbt_cloud.module.projects_v2[0].dbtcloud_project_repository.project_repositories["test_project"]
  to   = module.dbt_cloud.module.projects_v2[0].dbtcloud_project_repository.protected_project_repositories["test_project"]
}
'''


@pytest.fixture
def invalid_moved_tf() -> str:
    """Invalid moved block for error testing."""
    return '''# Invalid moved block - missing 'to' field
moved {
  from = module.dbt_cloud.dbtcloud_project.projects["test"]
  # Missing 'to' field
}
'''


# =============================================================================
# State File Fixtures
# =============================================================================

@pytest.fixture
def empty_terraform_state() -> Dict[str, Any]:
    """Empty Terraform state structure."""
    return {
        "version": 4,
        "terraform_version": "1.5.0",
        "serial": 1,
        "lineage": "test-lineage-empty",
        "outputs": {},
        "resources": [],
    }


@pytest.fixture
def sample_terraform_state() -> Dict[str, Any]:
    """Sample Terraform state with projects and repositories."""
    return {
        "version": 4,
        "terraform_version": "1.5.0",
        "serial": 5,
        "lineage": "test-lineage-sample",
        "outputs": {},
        "resources": [
            {
                "module": "module.dbt_cloud.module.projects_v2[0]",
                "mode": "managed",
                "type": "dbtcloud_project",
                "name": "projects",
                "provider": "provider[\"registry.terraform.io/dbt-labs/dbtcloud\"]",
                "instances": [
                    {
                        "index_key": "test_project",
                        "schema_version": 0,
                        "attributes": {
                            "id": "123456",
                            "name": "Test Project",
                        },
                    },
                ],
            },
            {
                "module": "module.dbt_cloud.module.projects_v2[0]",
                "mode": "managed",
                "type": "dbtcloud_repository",
                "name": "repositories",
                "provider": "provider[\"registry.terraform.io/dbt-labs/dbtcloud\"]",
                "instances": [
                    {
                        "index_key": "test_project",
                        "schema_version": 0,
                        "attributes": {
                            "id": "789",
                            "remote_url": "https://github.com/test/repo",
                        },
                    },
                ],
            },
            {
                "module": "module.dbt_cloud.module.projects_v2[0]",
                "mode": "managed",
                "type": "dbtcloud_project_repository",
                "name": "project_repositories",
                "provider": "provider[\"registry.terraform.io/dbt-labs/dbtcloud\"]",
                "instances": [
                    {
                        "index_key": "test_project",
                        "schema_version": 0,
                        "attributes": {
                            "id": "456",
                            "project_id": "123456",
                            "repository_id": "789",
                        },
                    },
                ],
            },
        ],
    }


@pytest.fixture
def protected_terraform_state() -> Dict[str, Any]:
    """Terraform state with resources in protected blocks."""
    return {
        "version": 4,
        "terraform_version": "1.5.0",
        "serial": 10,
        "lineage": "test-lineage-protected",
        "outputs": {},
        "resources": [
            {
                "module": "module.dbt_cloud.module.projects_v2[0]",
                "mode": "managed",
                "type": "dbtcloud_project",
                "name": "protected_projects",  # Protected block
                "provider": "provider[\"registry.terraform.io/dbt-labs/dbtcloud\"]",
                "instances": [
                    {
                        "index_key": "protected_proj",
                        "schema_version": 0,
                        "attributes": {
                            "id": "111",
                            "name": "Protected Project",
                        },
                    },
                ],
            },
            {
                "module": "module.dbt_cloud.module.projects_v2[0]",
                "mode": "managed",
                "type": "dbtcloud_project",
                "name": "projects",  # Unprotected block
                "provider": "provider[\"registry.terraform.io/dbt-labs/dbtcloud\"]",
                "instances": [
                    {
                        "index_key": "unprotected_proj",
                        "schema_version": 0,
                        "attributes": {
                            "id": "222",
                            "name": "Unprotected Project",
                        },
                    },
                ],
            },
        ],
    }


# =============================================================================
# Setup Fixtures
# =============================================================================

@pytest.fixture
def setup_minimal_terraform(
    terraform_dir: Path,
    minimal_providers_tf: str,
    minimal_main_tf: str,
) -> Path:
    """Set up minimal Terraform configuration for testing.
    
    Returns:
        Path to the terraform directory
    """
    (terraform_dir / "providers.tf").write_text(minimal_providers_tf)
    (terraform_dir / "main.tf").write_text(minimal_main_tf)
    return terraform_dir


@pytest.fixture
def setup_terraform_with_moves(
    terraform_dir: Path,
    minimal_providers_tf: str,
    minimal_main_tf: str,
    protection_moves_tf: str,
) -> Path:
    """Set up Terraform configuration with protection moves.
    
    Returns:
        Path to the terraform directory
    """
    (terraform_dir / "providers.tf").write_text(minimal_providers_tf)
    (terraform_dir / "main.tf").write_text(minimal_main_tf)
    (terraform_dir / "protection_moves.tf").write_text(protection_moves_tf)
    return terraform_dir


@pytest.fixture
def setup_terraform_with_state(
    terraform_dir: Path,
    minimal_providers_tf: str,
    minimal_main_tf: str,
    sample_terraform_state: Dict[str, Any],
) -> Path:
    """Set up Terraform with a pre-existing state file.
    
    Returns:
        Path to the terraform directory
    """
    (terraform_dir / "providers.tf").write_text(minimal_providers_tf)
    (terraform_dir / "main.tf").write_text(minimal_main_tf)
    (terraform_dir / "terraform.tfstate").write_text(json.dumps(sample_terraform_state, indent=2))
    return terraform_dir


@pytest.fixture
def setup_invalid_terraform(
    terraform_dir: Path,
    minimal_providers_tf: str,
    invalid_moved_tf: str,
) -> Path:
    """Set up invalid Terraform configuration for error testing.
    
    Returns:
        Path to the terraform directory
    """
    (terraform_dir / "providers.tf").write_text(minimal_providers_tf)
    (terraform_dir / "invalid_moved.tf").write_text(invalid_moved_tf)
    return terraform_dir


# =============================================================================
# Copy Fixture Helpers
# =============================================================================

@pytest.fixture
def copy_valid_config(terraform_dir: Path, valid_config_dir: Path) -> Path:
    """Copy valid_config fixtures to test terraform directory.
    
    Returns:
        Path to the terraform directory with copied config
    """
    if valid_config_dir.exists():
        for file in valid_config_dir.glob("*.tf"):
            shutil.copy(file, terraform_dir / file.name)
    return terraform_dir


@pytest.fixture
def copy_invalid_config(terraform_dir: Path, invalid_config_dir: Path) -> Path:
    """Copy invalid_config fixtures to test terraform directory.
    
    Returns:
        Path to the terraform directory with copied config
    """
    if invalid_config_dir.exists():
        for file in invalid_config_dir.glob("*.tf"):
            shutil.copy(file, terraform_dir / file.name)
    return terraform_dir


# =============================================================================
# Utility Functions
# =============================================================================

def write_state_file(path: Path, state: Dict[str, Any]) -> Path:
    """Write a Terraform state file.
    
    Args:
        path: Path to write state file
        state: State dictionary
        
    Returns:
        Path to the written state file
    """
    state_file = path / "terraform.tfstate"
    state_file.write_text(json.dumps(state, indent=2))
    return state_file


def read_state_file(path: Path) -> Dict[str, Any]:
    """Read a Terraform state file.
    
    Args:
        path: Path containing state file
        
    Returns:
        State dictionary
    """
    state_file = path / "terraform.tfstate"
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {}


def create_moved_block(from_addr: str, to_addr: str) -> str:
    """Generate a Terraform moved block.
    
    Args:
        from_addr: Source resource address
        to_addr: Destination resource address
        
    Returns:
        HCL moved block string
    """
    return f'''moved {{
  from = {from_addr}
  to   = {to_addr}
}}
'''
