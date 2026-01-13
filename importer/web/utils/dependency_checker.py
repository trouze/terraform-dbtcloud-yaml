"""Dependency checker for verifying required tools and packages."""

import importlib.util
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple


class DependencyStatus(Enum):
    """Status of a dependency check."""
    OK = "ok"
    MISSING = "missing"
    ERROR = "error"
    OUTDATED = "outdated"


@dataclass
class DependencyResult:
    """Result of a dependency check."""
    name: str
    status: DependencyStatus
    version: Optional[str] = None
    message: Optional[str] = None
    install_command: Optional[str] = None
    install_url: Optional[str] = None


def check_terraform() -> DependencyResult:
    """Check if Terraform CLI is installed and get version."""
    try:
        result = subprocess.run(
            ["terraform", "version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # Parse version from output like "Terraform v1.6.0"
            match = re.search(r"Terraform v(\d+\.\d+\.\d+)", result.stdout)
            version = match.group(1) if match else "unknown"
            return DependencyResult(
                name="Terraform CLI",
                status=DependencyStatus.OK,
                version=version,
                message=f"Terraform v{version} installed"
            )
        else:
            return DependencyResult(
                name="Terraform CLI",
                status=DependencyStatus.ERROR,
                message=f"Error running terraform: {result.stderr}",
                install_command="brew install terraform",
                install_url="https://developer.hashicorp.com/terraform/downloads"
            )
    except FileNotFoundError:
        return DependencyResult(
            name="Terraform CLI",
            status=DependencyStatus.MISSING,
            message="Terraform not found in PATH",
            install_command="brew install terraform",
            install_url="https://developer.hashicorp.com/terraform/downloads"
        )
    except subprocess.TimeoutExpired:
        return DependencyResult(
            name="Terraform CLI",
            status=DependencyStatus.ERROR,
            message="Terraform command timed out"
        )
    except Exception as e:
        return DependencyResult(
            name="Terraform CLI",
            status=DependencyStatus.ERROR,
            message=str(e)
        )


def check_dbt_cloud_provider() -> DependencyResult:
    """Check if dbt Cloud Terraform provider is available."""
    # Check common provider locations
    home = Path.home()
    provider_paths = [
        home / ".terraform.d" / "plugins",
        home / ".terraform.d" / "plugin-cache",
        Path(".terraform") / "providers",
    ]
    
    provider_found = False
    provider_version = None
    
    # First, try to find in local .terraform directory
    local_tf = Path(".terraform")
    if local_tf.exists():
        for path in local_tf.rglob("*dbtcloud*"):
            if path.is_dir() or path.is_file():
                provider_found = True
                # Try to extract version from path
                match = re.search(r"(\d+\.\d+\.\d+)", str(path))
                if match:
                    provider_version = match.group(1)
                break
    
    # Check global plugin directories
    if not provider_found:
        for base_path in provider_paths:
            if base_path.exists():
                for path in base_path.rglob("*dbtcloud*"):
                    if path.is_dir() or path.is_file():
                        provider_found = True
                        match = re.search(r"(\d+\.\d+\.\d+)", str(path))
                        if match:
                            provider_version = match.group(1)
                        break
            if provider_found:
                break
    
    # Also check by running terraform providers if in a terraform directory
    if not provider_found:
        try:
            result = subprocess.run(
                ["terraform", "providers"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if "dbtcloud" in result.stdout.lower() or "dbt-labs/dbtcloud" in result.stdout:
                provider_found = True
                match = re.search(r"dbtcloud.*?(\d+\.\d+\.\d+)", result.stdout)
                if match:
                    provider_version = match.group(1)
        except Exception:
            pass
    
    if provider_found:
        return DependencyResult(
            name="dbt Cloud Provider",
            status=DependencyStatus.OK,
            version=provider_version,
            message=f"Provider v{provider_version}" if provider_version else "Provider found"
        )
    else:
        return DependencyResult(
            name="dbt Cloud Provider",
            status=DependencyStatus.MISSING,
            message="Provider not initialized. Run 'terraform init' in project directory.",
            install_command="terraform init",
            install_url="https://registry.terraform.io/providers/dbt-labs/dbtcloud/latest"
        )


def check_git() -> DependencyResult:
    """Check if Git CLI is installed and get version."""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            # Parse version from output like "git version 2.39.0"
            match = re.search(r"git version (\d+\.\d+\.\d+)", result.stdout)
            version = match.group(1) if match else "unknown"
            return DependencyResult(
                name="Git CLI",
                status=DependencyStatus.OK,
                version=version,
                message=f"Git v{version} installed"
            )
        else:
            return DependencyResult(
                name="Git CLI",
                status=DependencyStatus.ERROR,
                message=f"Error running git: {result.stderr}",
                install_command="brew install git",
                install_url="https://git-scm.com/downloads"
            )
    except FileNotFoundError:
        return DependencyResult(
            name="Git CLI",
            status=DependencyStatus.MISSING,
            message="Git not found in PATH",
            install_command="brew install git",
            install_url="https://git-scm.com/downloads"
        )
    except Exception as e:
        return DependencyResult(
            name="Git CLI",
            status=DependencyStatus.ERROR,
            message=str(e)
        )


# Required Python packages for the importer
REQUIRED_PACKAGES = [
    ("httpx", "httpx"),
    ("dotenv", "python-dotenv"),
    ("pydantic", "pydantic"),
    ("rich", "rich"),
    ("typer", "typer"),
    ("slugify", "python-slugify"),
    ("click", "click"),
    ("yaml", "PyYAML"),
    ("InquirerPy", "InquirerPy"),
    ("nicegui", "nicegui"),
    ("pandas", "pandas"),
    ("plotly", "plotly"),
]


def check_python_packages() -> Tuple[DependencyResult, List[Tuple[str, str, bool]]]:
    """Check if required Python packages are installed.
    
    Returns:
        Tuple of (overall result, list of (import_name, pip_name, is_installed))
    """
    package_status = []
    missing_count = 0
    
    for import_name, pip_name in REQUIRED_PACKAGES:
        spec = importlib.util.find_spec(import_name)
        is_installed = spec is not None
        package_status.append((import_name, pip_name, is_installed))
        if not is_installed:
            missing_count += 1
    
    total = len(REQUIRED_PACKAGES)
    installed = total - missing_count
    
    if missing_count == 0:
        result = DependencyResult(
            name="Python Packages",
            status=DependencyStatus.OK,
            version=f"{installed}/{total}",
            message=f"All {total} packages installed"
        )
    else:
        missing_packages = [pip for _, pip, installed in package_status if not installed]
        result = DependencyResult(
            name="Python Packages",
            status=DependencyStatus.MISSING,
            version=f"{installed}/{total}",
            message=f"Missing: {', '.join(missing_packages)}",
            install_command=f"pip install {' '.join(missing_packages)}"
        )
    
    return result, package_status


def install_python_packages(packages: Optional[List[str]] = None) -> Tuple[bool, str]:
    """Install Python packages using pip.
    
    Args:
        packages: List of package names to install. If None, installs from requirements.txt
        
    Returns:
        Tuple of (success, message)
    """
    try:
        if packages:
            cmd = [sys.executable, "-m", "pip", "install"] + packages
        else:
            # Install from requirements.txt
            requirements_path = Path(__file__).parent.parent.parent / "requirements.txt"
            if not requirements_path.exists():
                return False, f"requirements.txt not found at {requirements_path}"
            cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for installs
        )
        
        if result.returncode == 0:
            return True, "Packages installed successfully"
        else:
            return False, f"Installation failed: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return False, "Installation timed out after 5 minutes"
    except Exception as e:
        return False, f"Installation error: {str(e)}"


def run_all_checks() -> List[DependencyResult]:
    """Run all dependency checks and return results."""
    results = []
    
    # Terraform
    results.append(check_terraform())
    
    # dbt Cloud Provider
    results.append(check_dbt_cloud_provider())
    
    # Python packages (just the summary result)
    python_result, _ = check_python_packages()
    results.append(python_result)
    
    # Git
    results.append(check_git())
    
    return results


def get_overall_status(results: List[DependencyResult]) -> DependencyStatus:
    """Get overall status from a list of results."""
    statuses = [r.status for r in results]
    
    if DependencyStatus.ERROR in statuses:
        return DependencyStatus.ERROR
    elif DependencyStatus.MISSING in statuses:
        return DependencyStatus.MISSING
    elif DependencyStatus.OUTDATED in statuses:
        return DependencyStatus.OUTDATED
    else:
        return DependencyStatus.OK
