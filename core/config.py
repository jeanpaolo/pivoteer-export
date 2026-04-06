import yaml
import os

CONFIG_PATH = os.path.expanduser("~/.pivoteer/config.yaml")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"profiles": {}}
    with open(CONFIG_PATH, 'r') as f:
        return yaml.safe_load(f) or {"profiles": {}}

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

def get_profile(profile_name):
    config = load_config()
    return config.get("profiles", {}).get(profile_name)

def interactive_setup():
    print("--- Pivoteer Profile Setup ---")
    profile_name = input("Profile Name (e.g., azure-prod, rds-dev): ").strip()
    host = input("Host/Endpoint: ").strip()
    port = input("Port [1433]: ").strip() or "1433"
    user = input("Username: ").strip()
    password = input("Password: ").strip()
    
    config = load_config()
    if "profiles" not in config:
        config["profiles"] = {}
        
    config["profiles"][profile_name] = {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password
    }
    
    save_config(config)
    print(f"Profile '{profile_name}' saved successfully to {CONFIG_PATH}")
