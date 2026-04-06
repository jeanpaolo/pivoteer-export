import pytest
import os
import yaml
from core.config import load_config, save_config, get_profile

def test_save_and_load_config(tmp_path, monkeypatch):
    # Mock CONFIG_PATH to use a temporary file
    config_file = tmp_path / "config.yaml"
    monkeypatch.setattr("core.config.CONFIG_PATH", str(config_file))
    
    config = {
        "profiles": {
            "test-profile": {
                "host": "localhost",
                "port": 1433,
                "user": "sa",
                "password": "password123"
            }
        }
    }
    
    save_config(config)
    assert os.path.exists(config_file)
    
    loaded_config = load_config()
    assert loaded_config == config
    
    profile = get_profile("test-profile")
    assert profile["host"] == "localhost"
    assert profile["port"] == 1433

def test_load_missing_config(tmp_path, monkeypatch):
    config_file = tmp_path / "missing.yaml"
    monkeypatch.setattr("core.config.CONFIG_PATH", str(config_file))
    
    loaded_config = load_config()
    assert loaded_config == {"profiles": {}}
