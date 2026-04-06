#!/usr/bin/env python3
"""
bootstrap.py

Auto-installs required Python packages for Pivoteer.
Called at the top of pivoteer.py before any project imports.

Packages:
  - pyodbc      : SQL Server ODBC connectivity
  - apscheduler : Background task scheduling
  - pyyaml      : YAML config file parsing

System requirements (installed separately if missing):
  - unixodbc    : Required by pyodbc on Linux
"""

import subprocess
import sys
import os

_REQUIRED = ["pyodbc", "apscheduler", "pyyaml"]

def _is_installed(package):
    import importlib
    pkg_map = {"pyyaml": "yaml", "apscheduler": "apscheduler", "pyodbc": "pyodbc"}
    try:
        importlib.import_module(pkg_map.get(package, package))
        return True
    except ImportError:
        return False

def install_dependencies(quiet=False):
    """
    Checks for and installs missing Python dependencies.
    Returns True if all dependencies are available after the attempt.
    """
    missing = [p for p in _REQUIRED if not _is_installed(p)]
    
    if not missing:
        return True
        
    if not quiet:
        print(f"Installing missing dependencies: {', '.join(missing)}")
        
    # Prefer --user install unless inside a virtualenv
    in_venv = hasattr(sys, 'real_prefix') or (sys.base_prefix != sys.prefix)
    cmd = [sys.executable, "-m", "pip", "install"] + missing
    if not in_venv:
        cmd.append("--user")
        
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL if quiet else None)
    except subprocess.CalledProcessError:
        # Retry with sudo as a last resort
        try:
            subprocess.check_call(["sudo", sys.executable, "-m", "pip", "install"] + missing)
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Could not install dependencies: {e}", file=sys.stdout)
            return False
            
    # Verify
    still_missing = [p for p in missing if not _is_installed(p)]
    if still_missing:
        print(f"ERROR: Still missing after install: {still_missing}", file=sys.stdout)
        return False
        
    return True

if __name__ == "__main__":
    success = install_dependencies()
    sys.exit(0 if success else 1)
