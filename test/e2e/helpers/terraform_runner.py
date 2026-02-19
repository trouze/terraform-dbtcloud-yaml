"""Terraform Runner for E2E Tests.

This module provides a Terraform execution wrapper that:
- Runs real terraform init and terraform plan
- Mocks terraform apply and terraform destroy for safety
- Provides structured result handling
- Supports test isolation

Reference: PRD 11.01-Protection-Workflow-Testing.md Section 1.3
"""

import json
import os
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class TerraformResult:
    """Result of a Terraform operation."""
    success: bool
    command: str
    stdout: str
    stderr: str
    return_code: int
    mocked: bool = False
    
    @property
    def output(self) -> str:
        """Combined output for display."""
        return f"{self.stdout}\n{self.stderr}".strip()


class TerraformRunner:
    """Runs Terraform commands with selective mocking.
    
    Strategy:
    - terraform init: REAL - validates provider config
    - terraform validate: REAL - validates HCL syntax
    - terraform plan: REAL - validates moved blocks, shows changes
    - terraform apply: MOCKED - simulates state updates
    - terraform destroy: MOCKED - simulates resource removal
    """
    
    def __init__(
        self,
        working_dir: Path,
        mock_apply: bool = True,
        mock_destroy: bool = True,
    ):
        """Initialize the runner.
        
        Args:
            working_dir: Directory containing Terraform files
            mock_apply: Whether to mock apply operations
            mock_destroy: Whether to mock destroy operations
        """
        self.working_dir = Path(working_dir)
        self.mock_apply = mock_apply
        self.mock_destroy = mock_destroy
        
        # State tracking for mocked operations
        self._applied_changes: List[str] = []
        self._destroyed_resources: List[str] = []
    
    # =========================================================================
    # Real Operations
    # =========================================================================
    
    def init(self, upgrade: bool = False) -> TerraformResult:
        """Run terraform init (real operation).
        
        Args:
            upgrade: Whether to upgrade providers
            
        Returns:
            TerraformResult
        """
        cmd = ["terraform", "init"]
        if upgrade:
            cmd.append("-upgrade")
        
        return self._run_command(cmd)
    
    def validate(self) -> TerraformResult:
        """Run terraform validate (real operation).
        
        Returns:
            TerraformResult
        """
        return self._run_command(["terraform", "validate"])
    
    def plan(
        self,
        out_file: Optional[str] = None,
        json_output: bool = False,
    ) -> TerraformResult:
        """Run terraform plan (real operation).
        
        Args:
            out_file: File to save plan (e.g., "tfplan")
            json_output: Whether to output JSON format
            
        Returns:
            TerraformResult
        """
        cmd = ["terraform", "plan"]
        
        if out_file:
            cmd.extend(["-out", out_file])
        
        if json_output:
            cmd.append("-json")
        
        return self._run_command(cmd)
    
    def show_plan(self, plan_file: str = "tfplan") -> TerraformResult:
        """Show plan in JSON format (real operation).
        
        Args:
            plan_file: Path to the plan file
            
        Returns:
            TerraformResult with JSON plan in stdout
        """
        return self._run_command(["terraform", "show", "-json", plan_file])
    
    # =========================================================================
    # Mocked Operations
    # =========================================================================
    
    def apply(self, auto_approve: bool = True) -> TerraformResult:
        """Run terraform apply (mocked by default).
        
        When mocked:
        1. Parses the plan to understand changes
        2. Updates local state simulation
        3. Removes moves file if exists
        4. Returns success result
        
        Args:
            auto_approve: Skip approval prompt
            
        Returns:
            TerraformResult
        """
        if self.mock_apply:
            return self._mocked_apply()
        
        cmd = ["terraform", "apply"]
        if auto_approve:
            cmd.append("-auto-approve")
        
        return self._run_command(cmd)
    
    def destroy(
        self,
        targets: Optional[List[str]] = None,
        auto_approve: bool = True,
    ) -> TerraformResult:
        """Run terraform destroy (mocked by default).
        
        When mocked:
        1. Records destroyed resources
        2. Updates local state simulation
        3. Returns success result
        
        Args:
            targets: Specific resources to destroy
            auto_approve: Skip approval prompt
            
        Returns:
            TerraformResult
        """
        if self.mock_destroy:
            return self._mocked_destroy(targets)
        
        cmd = ["terraform", "destroy"]
        if auto_approve:
            cmd.append("-auto-approve")
        
        if targets:
            for target in targets:
                cmd.extend(["-target", target])
        
        return self._run_command(cmd)
    
    def _mocked_apply(self) -> TerraformResult:
        """Simulate terraform apply.
        
        Returns:
            Mocked TerraformResult
        """
        # Read plan file if exists
        plan_file = self.working_dir / "tfplan"
        plan_json_file = self.working_dir / "plan.json"
        
        changes_applied = []
        
        if plan_file.exists():
            # Export plan to JSON for parsing
            result = self._run_command(["terraform", "show", "-json", str(plan_file)])
            if result.success:
                try:
                    plan_data = json.loads(result.stdout)
                    changes = plan_data.get("resource_changes", [])
                    
                    for change in changes:
                        address = change.get("address", "")
                        actions = change.get("change", {}).get("actions", [])
                        
                        if "create" in actions or "update" in actions:
                            changes_applied.append(f"Applied: {address}")
                        elif "delete" in actions:
                            changes_applied.append(f"Destroyed: {address}")
                
                except json.JSONDecodeError:
                    pass
        
        # Remove moves file after "apply"
        moves_file = self.working_dir / "protection_moves.tf"
        if moves_file.exists():
            moves_file.unlink()
            changes_applied.append("Removed: protection_moves.tf")
        
        # Remove plan file
        if plan_file.exists():
            plan_file.unlink()
        if plan_json_file.exists():
            plan_json_file.unlink()
        
        self._applied_changes.extend(changes_applied)
        
        output = "Apply complete! (mocked - no cloud changes)\n"
        output += f"Resources: {len(changes_applied)} applied\n"
        output += "\n".join(changes_applied)
        
        return TerraformResult(
            success=True,
            command="terraform apply -auto-approve",
            stdout=output,
            stderr="",
            return_code=0,
            mocked=True,
        )
    
    def _mocked_destroy(
        self,
        targets: Optional[List[str]] = None,
    ) -> TerraformResult:
        """Simulate terraform destroy.
        
        Args:
            targets: Resources to destroy
            
        Returns:
            Mocked TerraformResult
        """
        destroyed = []
        
        if targets:
            destroyed.extend(targets)
        else:
            # Simulate destroying all resources in state
            state_file = self.working_dir / "terraform.tfstate"
            if state_file.exists():
                state = json.loads(state_file.read_text())
                for resource in state.get("resources", []):
                    for instance in resource.get("instances", []):
                        address = f"{resource['type']}.{resource['name']}[{instance.get('index_key', 0)}]"
                        destroyed.append(address)
        
        self._destroyed_resources.extend(destroyed)
        
        output = f"Destroy complete! (mocked - no cloud changes)\n"
        output += f"Resources: {len(destroyed)} destroyed\n"
        output += "\n".join(f"  - {r}" for r in destroyed)
        
        return TerraformResult(
            success=True,
            command="terraform destroy -auto-approve",
            stdout=output,
            stderr="",
            return_code=0,
            mocked=True,
        )
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _run_command(self, cmd: List[str]) -> TerraformResult:
        """Run a Terraform command.
        
        Args:
            cmd: Command and arguments
            
        Returns:
            TerraformResult
        """
        try:
            env = os.environ.copy()
            # Provide deterministic defaults so terraform plan/validate tests don't
            # fail on missing provider credentials in local environments.
            env.setdefault("TF_VAR_dbt_account_id", "13")
            env.setdefault("TF_VAR_dbt_token", "test-token")
            env.setdefault("TF_VAR_dbt_host_url", "https://cloud.getdbt.com")
            env.setdefault("DBTCLOUD_ACCOUNT_ID", "13")
            env.setdefault("DBTCLOUD_TOKEN", "test-token")
            env.setdefault("DBTCLOUD_HOST_URL", "https://cloud.getdbt.com")
            env.setdefault("DBT_CLOUD_ACCOUNT_ID", "13")
            env.setdefault("DBT_CLOUD_TOKEN", "test-token")
            env.setdefault("DBT_CLOUD_HOST_URL", "https://cloud.getdbt.com")

            result = subprocess.run(
                cmd,
                cwd=str(self.working_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )
            
            return TerraformResult(
                success=result.returncode == 0,
                command=" ".join(cmd),
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
            )
        
        except subprocess.TimeoutExpired:
            return TerraformResult(
                success=False,
                command=" ".join(cmd),
                stdout="",
                stderr="Command timed out after 300 seconds",
                return_code=-1,
            )
        
        except Exception as e:
            return TerraformResult(
                success=False,
                command=" ".join(cmd),
                stdout="",
                stderr=str(e),
                return_code=-1,
            )
    
    def get_applied_changes(self) -> List[str]:
        """Get list of changes applied in mocked apply operations."""
        return list(self._applied_changes)
    
    def get_destroyed_resources(self) -> List[str]:
        """Get list of resources destroyed in mocked operations."""
        return list(self._destroyed_resources)
    
    def reset_tracking(self) -> None:
        """Reset change tracking."""
        self._applied_changes = []
        self._destroyed_resources = []
    
    # =========================================================================
    # Convenience Methods
    # =========================================================================
    
    def full_init_plan_cycle(self) -> Dict[str, TerraformResult]:
        """Run init → validate → plan cycle.
        
        Returns:
            Dict of operation names to results
        """
        results = {}
        
        results["init"] = self.init()
        if not results["init"].success:
            return results
        
        results["validate"] = self.validate()
        if not results["validate"].success:
            return results
        
        results["plan"] = self.plan(out_file="tfplan")
        
        return results
    
    def full_apply_cycle(self) -> Dict[str, TerraformResult]:
        """Run init → plan → apply cycle.
        
        Returns:
            Dict of operation names to results
        """
        results = self.full_init_plan_cycle()
        
        if all(r.success for r in results.values()):
            results["apply"] = self.apply()
        
        return results


# =============================================================================
# Test Environment Setup
# =============================================================================

def create_test_terraform_environment(
    workspace: Path,
    providers_content: Optional[str] = None,
    main_content: Optional[str] = None,
) -> Path:
    """Create an isolated Terraform test environment.
    
    Args:
        workspace: Base workspace path
        providers_content: Custom providers.tf content
        main_content: Custom main.tf content
        
    Returns:
        Path to the terraform directory
    """
    tf_dir = workspace / "terraform"
    tf_dir.mkdir(parents=True, exist_ok=True)
    
    # Default providers.tf with local backend
    if providers_content is None:
        providers_content = """
terraform {
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
  # Configuration will come from environment variables
  # or provider block in test setup
}
"""
    
    # Default main.tf placeholder
    if main_content is None:
        main_content = """
# Test Terraform configuration
# This file is generated for testing purposes

variable "test_mode" {
  description = "Whether running in test mode"
  type        = bool
  default     = true
}
"""
    
    (tf_dir / "providers.tf").write_text(providers_content)
    (tf_dir / "main.tf").write_text(main_content)
    
    return tf_dir
