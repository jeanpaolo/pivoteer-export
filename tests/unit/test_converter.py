import pytest
from core.converter import (
    convert_azure_ad_login,
    convert_ledger_table,
    strip_key_vault_refs,
    drop_unsupported_features,
    apply_all_conversions
)

def test_convert_azure_ad_login():
    sql = "CREATE LOGIN [user@domain.com] FROM EXTERNAL PROVIDER"
    expected = "CREATE LOGIN [user@domain.com] WITH PASSWORD = 'ChangeMe123!' /* CONVERTED FROM AZURE AD */"
    assert convert_azure_ad_login(sql) == expected

def test_convert_ledger_table():
    sql = "CREATE TABLE t1 (id INT) WITH (SYSTEM_VERSIONING = ON (HISTORY_TABLE = t1_hist), LEDGER = ON)"
    expected = "CREATE TABLE t1 (id INT) WITH (SYSTEM_VERSIONING = ON (HISTORY_TABLE = t1_hist) /* LEDGER = ON REMOVED */)"
    assert convert_ledger_table(sql) == expected

def test_strip_key_vault_refs():
    sql = "CREATE COLUMN MASTER KEY MyCMK FROM PROVIDER = 'AZURE_KEY_VAULT' KEY_PATH = 'https://myvault.vault.azure.net/keys/mykey'"
    expected = "CREATE COLUMN MASTER KEY MyCMK FROM PROVIDER = 'MSSQL_CERTIFICATE_STORE' KEY_PATH = 'Current User/Personal/...' /* CONVERTED FROM AZURE KEY VAULT */"
    assert strip_key_vault_refs(sql) == expected

def test_drop_unsupported_features():
    sql = """
    CREATE EXTERNAL DATA SOURCE MyEDS WITH (TYPE = RDBMS, LOCATION = 'myserver.database.windows.net');
    CREATE EXTERNAL TABLE MyET (id INT) WITH (DATA_SOURCE = MyEDS);
    ALTER TABLE MyTable SET ( REMOTE_DATA_ARCHIVE = ON (FILTER_PREDICATE = null, MIGRATION_STATE = OUTBOUND) );
    SELECT * FROM OPENROWSET(BULK 'data.csv', DATA_SOURCE = 'MyBlobStorage') AS Data;
    ALTER DATABASE MyDb ADD SECONDARY ON SERVER MySecondaryServer;
    """
    converted = drop_unsupported_features(sql)
    assert "/* ELASTIC QUERY DATA SOURCE DROPPED */" in converted
    assert "/* ELASTIC QUERY EXTERNAL TABLE DROPPED */" in converted
    assert "/* STRETCH DATABASE DROPPED */" in converted
    assert "/* OPENROWSET TO AZURE BLOB DROPPED */" in converted
    assert "/* GEO-REPLICATION DROPPED */" in converted

def test_apply_all_conversions():
    sql = "CREATE LOGIN [user@domain.com] FROM EXTERNAL PROVIDER; CREATE TABLE t1 (id INT) WITH (LEDGER = ON);"
    converted = apply_all_conversions(sql)
    assert "WITH PASSWORD = 'ChangeMe123!'" in converted
    assert "/* LEDGER = ON REMOVED */" in converted
