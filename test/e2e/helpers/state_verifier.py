"""State Verifier for E2E Tests.

This module provides utilities to verify the file system state
during and after workflow execution, including:
- Protection intent file verification
- YAML configuration verification
- Terraform moves file verification
- Terraform state verification

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.7
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

import yaml


@dataclass
class VerificationResult:
    """Result of a state verification check."""
    passed: bool
    message: str
    expected: Any = None
    actual: Any = None


class StateVerifier:
    """Verifies file system state for protection workflow tests.
    
    This class checks:
    - Intent file contents and structure
    - YAML configuration protection flags
    - Terraform moves file existence and content
    - Terraform state resource locations
    """
    
    def __init__(self, workspace_path: Path):
        """Initialize verifier with workspace path.
        
        Args:
            workspace_path: Path to the test workspace
        """
        self.workspace = workspace_path
        self.intent_file = workspace_path / "config" / "protection-intent.json"
        self.yaml_file = workspace_path / "config" / "dbt-cloud-config.yml"
        self.moves_file = workspace_path / "terraform" / "protection_moves.tf"
        self.state_file = workspace_path / "terraform" / "terraform.tfstate"
    
    # =========================================================================
    # Intent File Verification
    # =========================================================================
    
    def verify_intent_file_exists(self) -> VerificationResult:
        """Verify the intent file exists."""
        exists = self.intent_file.exists()
        return VerificationResult(
            passed=exists,
            message=f"Intent file {'exists' if exists else 'does not exist'}",
            expected=True,
            actual=exists,
        )
    
    def verify_intent_has_key(self, key: str) -> VerificationResult:
        """Verify the intent file contains a specific key.
        
        Args:
            key: Resource key to check
        """
        if not self.intent_file.exists():
            return VerificationResult(
                passed=False,
                message="Intent file does not exist",
            )
        
        data = json.loads(self.intent_file.read_text())
        intents = data.get("intent", {})
        has_key = key in intents
        
        return VerificationResult(
            passed=has_key,
            message=f"Key '{key}' {'found' if has_key else 'not found'} in intent file",
            expected=True,
            actual=has_key,
        )
    
    def verify_intent_protection_value(
        self,
        key: str,
        expected_protected: bool,
    ) -> VerificationResult:
        """Verify a specific intent has the expected protection value.
        
        Args:
            key: Resource key
            expected_protected: Expected protection status
        """
        if not self.intent_file.exists():
            return VerificationResult(
                passed=False,
                message="Intent file does not exist",
            )
        
        data = json.loads(self.intent_file.read_text())
        intent = data.get("intent", {}).get(key)
        
        if intent is None:
            return VerificationResult(
                passed=False,
                message=f"Key '{key}' not found in intent file",
                expected=expected_protected,
                actual=None,
            )
        
        actual = intent.get("protected")
        passed = actual == expected_protected
        
        return VerificationResult(
            passed=passed,
            message=f"Intent '{key}' protected={actual} (expected {expected_protected})",
            expected=expected_protected,
            actual=actual,
        )
    
    def verify_intent_applied_to_yaml(
        self,
        key: str,
        expected: bool,
    ) -> VerificationResult:
        """Verify an intent's applied_to_yaml flag.
        
        Args:
            key: Resource key
            expected: Expected applied_to_yaml value
        """
        if not self.intent_file.exists():
            return VerificationResult(
                passed=False,
                message="Intent file does not exist",
            )
        
        data = json.loads(self.intent_file.read_text())
        intent = data.get("intent", {}).get(key)
        
        if intent is None:
            return VerificationResult(
                passed=False,
                message=f"Key '{key}' not found in intent file",
            )
        
        actual = intent.get("applied_to_yaml", False)
        passed = actual == expected
        
        return VerificationResult(
            passed=passed,
            message=f"Intent '{key}' applied_to_yaml={actual} (expected {expected})",
            expected=expected,
            actual=actual,
        )
    
    def get_all_pending_intents(self) -> Set[str]:
        """Get all intents that are not yet applied to YAML.
        
        Returns:
            Set of resource keys with pending intents
        """
        if not self.intent_file.exists():
            return set()
        
        data = json.loads(self.intent_file.read_text())
        pending = set()
        
        for key, intent in data.get("intent", {}).items():
            if not intent.get("applied_to_yaml", False):
                pending.add(key)
        
        return pending
    
    # =========================================================================
    # YAML Configuration Verification
    # =========================================================================
    
    def verify_yaml_file_exists(self) -> VerificationResult:
        """Verify the YAML configuration file exists."""
        exists = self.yaml_file.exists()
        return VerificationResult(
            passed=exists,
            message=f"YAML file {'exists' if exists else 'does not exist'}",
            expected=True,
            actual=exists,
        )
    
    def verify_project_protection(
        self,
        project_key: str,
        expected_protected: bool,
    ) -> VerificationResult:
        """Verify a project's protection status in YAML.
        
        Args:
            project_key: Project key
            expected_protected: Expected protection status
        """
        if not self.yaml_file.exists():
            return VerificationResult(
                passed=False,
                message="YAML file does not exist",
            )
        
        config = yaml.safe_load(self.yaml_file.read_text())
        
        for project in config.get("projects", []):
            if project.get("key") == project_key:
                actual = project.get("protected", False)
                passed = actual == expected_protected
                
                return VerificationResult(
                    passed=passed,
                    message=f"Project '{project_key}' protected={actual} (expected {expected_protected})",
                    expected=expected_protected,
                    actual=actual,
                )
        
        return VerificationResult(
            passed=False,
            message=f"Project '{project_key}' not found in YAML",
        )
    
    def get_protected_projects(self) -> List[str]:
        """Get list of protected project keys from YAML.
        
        Returns:
            List of protected project keys
        """
        if not self.yaml_file.exists():
            return []
        
        config = yaml.safe_load(self.yaml_file.read_text())
        protected = []
        
        for project in config.get("projects", []):
            if project.get("protected", False):
                protected.append(project.get("key", ""))
        
        return protected
    
    # =========================================================================
    # Terraform Moves File Verification
    # =========================================================================
    
    def verify_moves_file_exists(self) -> VerificationResult:
        """Verify the protection_moves.tf file exists."""
        exists = self.moves_file.exists()
        return VerificationResult(
            passed=exists,
            message=f"Moves file {'exists' if exists else 'does not exist'}",
            expected=True,
            actual=exists,
        )
    
    def verify_moves_file_not_exists(self) -> VerificationResult:
        """Verify the protection_moves.tf file does NOT exist."""
        exists = self.moves_file.exists()
        return VerificationResult(
            passed=not exists,
            message=f"Moves file {'exists (should not)' if exists else 'correctly absent'}",
            expected=False,
            actual=exists,
        )
    
    def verify_moves_file_contains_resource(
        self,
        resource_key: str,
    ) -> VerificationResult:
        """Verify the moves file contains a moved block for a resource.
        
        Args:
            resource_key: Resource key to find
        """
        if not self.moves_file.exists():
            return VerificationResult(
                passed=False,
                message="Moves file does not exist",
            )
        
        content = self.moves_file.read_text()
        contains = resource_key in content
        
        return VerificationResult(
            passed=contains,
            message=f"Moves file {'contains' if contains else 'does not contain'} '{resource_key}'",
            expected=True,
            actual=contains,
        )
    
    def count_moved_blocks(self) -> int:
        """Count the number of moved blocks in the moves file.
        
        Returns:
            Number of 'moved {' blocks
        """
        if not self.moves_file.exists():
            return 0
        
        content = self.moves_file.read_text()
        return content.count("moved {")
    
    # =========================================================================
    # Terraform State Verification
    # =========================================================================
    
    def verify_state_file_exists(self) -> VerificationResult:
        """Verify the terraform.tfstate file exists."""
        exists = self.state_file.exists()
        return VerificationResult(
            passed=exists,
            message=f"State file {'exists' if exists else 'does not exist'}",
            expected=True,
            actual=exists,
        )
    
    def verify_resource_in_protected_block(
        self,
        resource_type: str,
        resource_key: str,
    ) -> VerificationResult:
        """Verify a resource is in a protected block in state.
        
        Args:
            resource_type: TF resource type (e.g., "dbtcloud_project")
            resource_key: Resource index key
        """
        if not self.state_file.exists():
            return VerificationResult(
                passed=False,
                message="State file does not exist",
            )
        
        state = json.loads(self.state_file.read_text())
        
        for resource in state.get("resources", []):
            if resource.get("type") != resource_type:
                continue
            
            # Check if in protected block
            name = resource.get("name", "")
            is_protected = "protected_" in name
            
            for instance in resource.get("instances", []):
                if instance.get("index_key") == resource_key:
                    return VerificationResult(
                        passed=is_protected,
                        message=f"Resource {resource_key} is in {'protected' if is_protected else 'unprotected'} block",
                        expected=True,
                        actual=is_protected,
                    )
        
        return VerificationResult(
            passed=False,
            message=f"Resource {resource_type}[{resource_key}] not found in state",
        )
    
    # =========================================================================
    # Composite Verifications
    # =========================================================================
    
    def verify_intent_yaml_consistency(
        self,
        key: str,
    ) -> VerificationResult:
        """Verify intent and YAML are consistent for a resource.
        
        If an intent is marked as applied_to_yaml, the YAML should
        reflect the intent's protection status.
        
        Args:
            key: Resource key (e.g., "PRJ:my_project")
        """
        if not self.intent_file.exists() or not self.yaml_file.exists():
            return VerificationResult(
                passed=False,
                message="Intent or YAML file does not exist",
            )
        
        intent_data = json.loads(self.intent_file.read_text())
        intent = intent_data.get("intent", {}).get(key)
        
        if not intent:
            return VerificationResult(
                passed=True,
                message=f"No intent for {key}, skipping consistency check",
            )
        
        if not intent.get("applied_to_yaml", False):
            return VerificationResult(
                passed=True,
                message=f"Intent for {key} not yet applied to YAML",
            )
        
        # Extract project key from prefixed key
        project_key = key.split(":", 1)[-1] if ":" in key else key
        
        yaml_config = yaml.safe_load(self.yaml_file.read_text())
        
        for project in yaml_config.get("projects", []):
            if project.get("key") == project_key:
                yaml_protected = project.get("protected", False)
                intent_protected = intent.get("protected", False)
                
                passed = yaml_protected == intent_protected
                return VerificationResult(
                    passed=passed,
                    message=f"Intent ({intent_protected}) and YAML ({yaml_protected}) {'match' if passed else 'mismatch'}",
                    expected=intent_protected,
                    actual=yaml_protected,
                )
        
        return VerificationResult(
            passed=False,
            message=f"Project {project_key} not found in YAML",
        )
    
    def run_all_invariant_checks(self) -> List[VerificationResult]:
        """Run all invariant verification checks.
        
        Returns:
            List of all verification results
        """
        results = []
        
        # Check file existence
        results.append(self.verify_intent_file_exists())
        results.append(self.verify_yaml_file_exists())
        
        # Check consistency for all intents
        if self.intent_file.exists():
            data = json.loads(self.intent_file.read_text())
            for key in data.get("intent", {}).keys():
                results.append(self.verify_intent_yaml_consistency(key))
        
        return results
    
    def assert_all_passed(self, results: List[VerificationResult]) -> None:
        """Assert all verification results passed.
        
        Args:
            results: List of verification results
            
        Raises:
            AssertionError: If any result failed
        """
        failures = [r for r in results if not r.passed]
        
        if failures:
            messages = [f.message for f in failures]
            raise AssertionError(
                f"{len(failures)} verification(s) failed:\n" +
                "\n".join(f"  - {m}" for m in messages)
            )
