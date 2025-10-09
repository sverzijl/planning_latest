#!/usr/bin/env python3
"""
CI/CD Setup Validation Script

This script validates the GitHub Actions CI/CD setup by checking:
1. Workflow file syntax and structure
2. Required files and directories
3. Python environment compatibility
4. Test execution
5. Dependencies

Usage:
    python .github/workflows/validate_setup.py
"""

import os
import sys
import subprocess
from pathlib import Path
import yaml


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.END}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


def validate_workflow_files():
    """Validate GitHub Actions workflow YAML files"""
    print_header("Validating Workflow Files")

    workflow_dir = Path(".github/workflows")
    if not workflow_dir.exists():
        print_error(f"Workflow directory not found: {workflow_dir}")
        return False

    print_success(f"Workflow directory exists: {workflow_dir}")

    # Expected workflow files
    workflow_files = {
        "tests.yml": "Main test workflow",
        "coverage.yml": "Coverage reporting workflow"
    }

    all_valid = True

    for filename, description in workflow_files.items():
        filepath = workflow_dir / filename

        if not filepath.exists():
            print_error(f"Missing workflow file: {filepath}")
            all_valid = False
            continue

        print_info(f"Found: {filename} - {description}")

        # Validate YAML syntax
        try:
            with open(filepath, 'r') as f:
                config = yaml.safe_load(f)

            # Check required keys
            if 'name' not in config:
                print_warning(f"  Missing 'name' in {filename}")

            if 'on' not in config:
                print_error(f"  Missing 'on' trigger in {filename}")
                all_valid = False

            if 'jobs' not in config:
                print_error(f"  Missing 'jobs' in {filename}")
                all_valid = False
            else:
                print_success(f"  Valid YAML with {len(config['jobs'])} job(s)")

        except yaml.YAMLError as e:
            print_error(f"  YAML syntax error in {filename}: {e}")
            all_valid = False
        except Exception as e:
            print_error(f"  Error reading {filename}: {e}")
            all_valid = False

    return all_valid


def validate_project_structure():
    """Validate required project files and directories"""
    print_header("Validating Project Structure")

    required_paths = {
        "src": "Source code directory",
        "tests": "Test directory",
        "requirements.txt": "Python dependencies",
        "README.md": "Project documentation",
        ".github/workflows": "CI/CD workflows"
    }

    all_exist = True

    for path_str, description in required_paths.items():
        path = Path(path_str)
        if path.exists():
            print_success(f"{path_str:30} - {description}")
        else:
            print_error(f"{path_str:30} - MISSING!")
            all_exist = False

    return all_exist


def validate_python_environment():
    """Validate Python version and key packages"""
    print_header("Validating Python Environment")

    # Check Python version
    version = sys.version_info
    print_info(f"Python version: {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print_error("Python 3.11+ required")
        return False
    else:
        print_success("Python version is compatible")

    # Check key packages
    required_packages = [
        'pytest',
        'pytest_cov',
        'pandas',
        'streamlit',
        'networkx',
        'pyomo'
    ]

    all_installed = True

    for package in required_packages:
        try:
            __import__(package)
            print_success(f"Package installed: {package}")
        except ImportError:
            print_error(f"Package missing: {package}")
            all_installed = False

    return all_installed


def validate_tests():
    """Validate test suite execution"""
    print_header("Validating Test Suite")

    print_info("Running pytest discovery...")

    try:
        # Run pytest in collection-only mode
        result = subprocess.run(
            ['pytest', '--collect-only', '-q'],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            # Parse output to count tests
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if 'test' in line.lower() and 'selected' in line.lower():
                    print_success(f"Test collection: {line.strip()}")
                    break
            else:
                print_success("Tests collected successfully")

            return True
        else:
            print_error("Test collection failed")
            print_error(result.stderr)
            return False

    except subprocess.TimeoutExpired:
        print_error("Test collection timed out")
        return False
    except FileNotFoundError:
        print_error("pytest not found - install with: pip install pytest")
        return False
    except Exception as e:
        print_error(f"Error running pytest: {e}")
        return False


def validate_pre_commit_config():
    """Validate pre-commit configuration"""
    print_header("Validating Pre-commit Configuration")

    config_file = Path(".pre-commit-config.yaml")

    if not config_file.exists():
        print_warning("Pre-commit config file not found (optional)")
        return True

    print_success(f"Pre-commit config exists: {config_file}")

    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)

        if 'repos' not in config:
            print_error("Invalid pre-commit config: missing 'repos'")
            return False

        print_success(f"Valid pre-commit config with {len(config['repos'])} repo(s)")

        # Check if pre-commit is installed
        try:
            result = subprocess.run(
                ['pre-commit', '--version'],
                capture_output=True,
                text=True
            )
            print_info(f"Pre-commit version: {result.stdout.strip()}")
        except FileNotFoundError:
            print_warning("pre-commit not installed (optional)")
            print_info("Install with: pip install pre-commit")

        return True

    except yaml.YAMLError as e:
        print_error(f"YAML syntax error in pre-commit config: {e}")
        return False
    except Exception as e:
        print_error(f"Error reading pre-commit config: {e}")
        return False


def validate_documentation():
    """Validate CI/CD documentation"""
    print_header("Validating Documentation")

    docs = {
        ".github/workflows/CI_CD_SETUP.md": "Detailed CI/CD setup guide",
        ".github/workflows/QUICK_START.md": "Developer quick start guide",
        "README.md": "Project README"
    }

    all_exist = True

    for doc_path, description in docs.items():
        path = Path(doc_path)
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print_success(f"{doc_path:50} ({size_kb:.1f} KB)")
        else:
            print_error(f"{doc_path:50} - MISSING!")
            all_exist = False

    return all_exist


def generate_summary(results):
    """Generate validation summary"""
    print_header("Validation Summary")

    total = len(results)
    passed = sum(results.values())
    failed = total - passed

    print(f"\nTotal checks: {total}")
    print(f"{Colors.GREEN}Passed: {passed}{Colors.END}")
    print(f"{Colors.RED}Failed: {failed}{Colors.END}")

    if failed == 0:
        print(f"\n{Colors.BOLD}{Colors.GREEN}✓ All validation checks passed!{Colors.END}")
        print(f"{Colors.GREEN}Your CI/CD setup is ready to use.{Colors.END}\n")
        return True
    else:
        print(f"\n{Colors.BOLD}{Colors.RED}✗ Some validation checks failed.{Colors.END}")
        print(f"{Colors.RED}Please fix the issues above before using CI/CD.{Colors.END}\n")
        return False


def main():
    """Main validation routine"""
    print(f"\n{Colors.BOLD}GitHub Actions CI/CD Setup Validator{Colors.END}")
    print(f"{Colors.BOLD}Planning Application - Test Automation Pipeline{Colors.END}")

    results = {
        "Workflow Files": validate_workflow_files(),
        "Project Structure": validate_project_structure(),
        "Python Environment": validate_python_environment(),
        "Test Suite": validate_tests(),
        "Pre-commit Config": validate_pre_commit_config(),
        "Documentation": validate_documentation()
    }

    success = generate_summary(results)

    if success:
        print_info("Next steps:")
        print("  1. Update badge URLs in README.md with your repository info")
        print("  2. Push to GitHub to trigger first workflow run")
        print("  3. Check GitHub Actions tab to monitor execution")
        print("  4. Configure branch protection rules (optional)")
        print("  5. Setup Codecov for coverage reporting (optional)")
        print(f"\nSee {Colors.BLUE}.github/workflows/CI_CD_SETUP.md{Colors.END} for details.\n")
        return 0
    else:
        print_info("Fix the issues above and run this script again.")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Validation cancelled by user{Colors.END}\n")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Unexpected error: {e}{Colors.END}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
