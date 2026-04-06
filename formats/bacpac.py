"""
formats/bacpac.py

BACPAC export via Microsoft SqlPackage CLI.
Auto-downloads SqlPackage if not found on PATH.
"""

import os
import subprocess
import sys
import urllib.request
import zipfile
import shutil

SQLPACKAGE_URL = (
    "https://aka.ms/sqlpackage-linux"
)
SQLPACKAGE_DIR = os.path.expanduser("~/.pivoteer/sqlpackage")
SQLPACKAGE_BIN = os.path.join(SQLPACKAGE_DIR, "sqlpackage")

def _ensure_sqlpackage():
    """Downloads and extracts SqlPackage if not already present."""
    if shutil.which("sqlpackage"):
        return "sqlpackage"
    if os.path.exists(SQLPACKAGE_BIN):
        return SQLPACKAGE_BIN
        
    print("SqlPackage not found. Downloading from Microsoft...")
    os.makedirs(SQLPACKAGE_DIR, exist_ok=True)
    zip_path = os.path.join(SQLPACKAGE_DIR, "sqlpackage.zip")
    
    urllib.request.urlretrieve(SQLPACKAGE_URL, zip_path)
    
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(SQLPACKAGE_DIR)
        
    os.chmod(SQLPACKAGE_BIN, 0o755)
    os.remove(zip_path)
    print(f"SqlPackage installed to {SQLPACKAGE_DIR}")
    return SQLPACKAGE_BIN

def export_bacpac(profile, database, output_path):
    """
    Exports a BACPAC file using SqlPackage.
    `profile` must be a dict with keys: host, port, user, password.
    """
    from core.config import get_profile
    
    p = get_profile(profile) if isinstance(profile, str) else profile
    if not p:
        raise ValueError(f"Profile '{profile}' not found.")
        
    sqlpackage = _ensure_sqlpackage()
    
    conn_str = (
        f"Server={p['host']},{p['port']};"
        f"Database={database};"
        f"User Id={p['user']};"
        f"Password={p['password']};"
        "Encrypt=True;TrustServerCertificate=True;"
    )
    
    cmd = [
        sqlpackage,
        "/Action:Export",
        f"/SourceConnectionString:{conn_str}",
        f"/TargetFile:{output_path}"
    ]
    
    print(f"Exporting BACPAC to {output_path}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"SqlPackage export failed with exit code {result.returncode}")
        
    print(f"BACPAC export complete: {output_path}")
    return output_path

def import_bacpac(profile, database, input_path):
    """
    Imports a BACPAC file using SqlPackage.
    """
    from core.config import get_profile
    
    p = get_profile(profile) if isinstance(profile, str) else profile
    if not p:
        raise ValueError(f"Profile '{profile}' not found.")
        
    sqlpackage = _ensure_sqlpackage()
    
    conn_str = (
        f"Server={p['host']},{p['port']};"
        f"Database={database};"
        f"User Id={p['user']};"
        f"Password={p['password']};"
        "Encrypt=True;TrustServerCertificate=True;"
    )
    
    cmd = [
        sqlpackage,
        "/Action:Import",
        f"/SourceFile:{input_path}",
        f"/TargetConnectionString:{conn_str}"
    ]
    
    print(f"Importing BACPAC from {input_path}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"SqlPackage import failed with exit code {result.returncode}")
        
    print(f"BACPAC import complete.")
