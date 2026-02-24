#!/usr/bin/env python
"""
Environment validation script for chipmunk-dashboard.

Run this after setting up your conda environment to ensure
everything is installed correctly.
"""

import sys


def check_import(module_name, package_name=None):
    """Try to import a module and report status."""
    if package_name is None:
        package_name = module_name

    try:
        __import__(module_name)
        print(f"✓ {package_name}")
        return True
    except ImportError as e:
        print(f"✗ {package_name}: {e}")
        return False


def check_version(module_name, package_name, expected_constraint=None):
    """Check module version."""
    try:
        module = __import__(module_name)
        version = getattr(module, "__version__", "unknown")
        status = f"✓ {package_name} version: {version}"

        if expected_constraint and version != "unknown":
            if expected_constraint in version:
                status += " (matches constraint)"
            else:
                status += f" (constraint: {expected_constraint})"

        print(status)
        return True
    except Exception as e:
        print(f"✗ {package_name}: {e}")
        return False


def main():
    """Run validation checks."""
    print("=" * 50)
    print("chipmunk-dashboard Environment Validation")
    print("=" * 50)
    print()

    print("Python version:", sys.version)
    print()

    print("Core dependencies:")
    print("-" * 30)
    checks = []

    # Core packages
    checks.append(check_import("dash", "dash"))
    checks.append(check_import("plotly", "plotly"))
    checks.append(check_import("pandas", "pandas"))
    checks.append(check_import("numpy", "numpy"))

    print()
    print("Database dependencies:")
    print("-" * 30)
    checks.append(check_version("datajoint", "datajoint", "0.14"))
    checks.append(check_import("labdata", "labdata"))

    print()
    print("Dashboard package:")
    print("-" * 30)
    checks.append(check_import("chipmunk_dashboard", "chipmunk-dashboard"))

    print()
    print("=" * 50)

    if all(checks):
        print("✓ All checks passed!")
        print()
        print("You can now run the dashboard with:")
        print("  chipmunk-dashboard run")
        return 0
    else:
        print("✗ Some checks failed. Please review errors above.")
        print()
        print("Try reinstalling the dashboard:")
        print("  pip install -e .")
        return 1


if __name__ == "__main__":
    sys.exit(main())
