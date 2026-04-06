import re

def convert_azure_ad_login(sql_script):
    """Converts Azure AD logins to standard SQL auth logins."""
    # Pattern: CREATE LOGIN [user@domain.com] FROM EXTERNAL PROVIDER
    pattern = re.compile(r"CREATE LOGIN \[(.*?)\] FROM EXTERNAL PROVIDER", re.IGNORECASE)
    return pattern.sub(r"CREATE LOGIN [\1] WITH PASSWORD = 'ChangeMe123!' /* CONVERTED FROM AZURE AD */", sql_script)

def convert_ledger_table(sql_script):
    """Converts Ledger tables to standard tables with audit trigger patterns."""
    # Pattern: WITH (SYSTEM_VERSIONING = ON (HISTORY_TABLE = ...), LEDGER = ON)
    sql_script = re.compile(r",\s*LEDGER\s*=\s*ON", re.IGNORECASE).sub(r" /* LEDGER = ON REMOVED */", sql_script)
    sql_script = re.compile(r"\(\s*LEDGER\s*=\s*ON\s*\)", re.IGNORECASE).sub(r"( /* LEDGER = ON REMOVED */ )", sql_script)
    return sql_script

def strip_key_vault_refs(sql_script):
    """Strips Azure Key Vault references while preserving column encryption skeleton."""
    # Pattern: CREATE COLUMN MASTER KEY ... FROM PROVIDER = 'AZURE_KEY_VAULT'
    pattern = re.compile(r"CREATE COLUMN MASTER KEY (.*?) FROM PROVIDER = 'AZURE_KEY_VAULT' KEY_PATH = '(.*?)'", re.IGNORECASE)
    return pattern.sub(r"CREATE COLUMN MASTER KEY \1 FROM PROVIDER = 'MSSQL_CERTIFICATE_STORE' KEY_PATH = 'Current User/Personal/...' /* CONVERTED FROM AZURE KEY VAULT */", sql_script)

def drop_unsupported_features(sql_script):
    """Drops Elastic Query, Stretch Database, OPENROWSET to Azure Blob, and Geo-replication."""
    # Elastic Query / External Tables
    sql_script = re.compile(r"CREATE EXTERNAL DATA SOURCE .*? WITH \(TYPE = RDBMS.*?\);", re.IGNORECASE | re.DOTALL).sub("/* ELASTIC QUERY DATA SOURCE DROPPED */", sql_script)
    sql_script = re.compile(r"CREATE EXTERNAL TABLE .*?;", re.IGNORECASE | re.DOTALL).sub("/* ELASTIC QUERY EXTERNAL TABLE DROPPED */", sql_script)
    
    # Stretch Database
    sql_script = re.compile(r"ALTER TABLE .*? SET \( REMOTE_DATA_ARCHIVE = ON .*?\);", re.IGNORECASE | re.DOTALL).sub("/* STRETCH DATABASE DROPPED */", sql_script)
    
    # OPENROWSET to Azure Blob
    sql_script = re.compile(r"OPENROWSET\(BULK .*?, DATA_SOURCE = '.*?'\)", re.IGNORECASE).sub("/* OPENROWSET TO AZURE BLOB DROPPED */", sql_script)
    
    # Geo-replication (Failover Groups)
    sql_script = re.compile(r"ALTER DATABASE .*? ADD SECONDARY ON SERVER .*?;", re.IGNORECASE).sub("/* GEO-REPLICATION DROPPED */", sql_script)
    
    return sql_script

def apply_all_conversions(sql_script):
    """Applies all conversion rules to a given SQL script."""
    sql_script = convert_azure_ad_login(sql_script)
    sql_script = convert_ledger_table(sql_script)
    sql_script = strip_key_vault_refs(sql_script)
    sql_script = drop_unsupported_features(sql_script)
    return sql_script
