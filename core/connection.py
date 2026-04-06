import pyodbc
from .config import get_profile

def get_connection(profile_name, database=None):
    profile = get_profile(profile_name)
    if not profile:
        raise ValueError(f"Profile '{profile_name}' not found in config.")
        
    driver = "{ODBC Driver 17 for SQL Server}"
    
    conn_str = (
        f"DRIVER={driver};"
        f"SERVER={profile['host']},{profile['port']};"
        f"UID={profile['user']};"
        f"PWD={profile['password']};"
    )
    
    if database:
        conn_str += f"DATABASE={database};"
        
    # Connect with auto-commit for administrative tasks
    conn = pyodbc.connect(conn_str, autocommit=True)
    return conn
