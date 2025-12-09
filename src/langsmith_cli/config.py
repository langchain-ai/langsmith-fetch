"""Configuration file management for LangSmith Fetch."""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any


CONFIG_DIR = Path.home() / ".langsmith-cli"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def _ensure_config_dir():
    """Ensure the config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """
    Load configuration from file.

    Returns:
        Dictionary of configuration values, empty dict if file doesn't exist
    """
    if not CONFIG_FILE.exists():
        return {}

    with open(CONFIG_FILE, "r") as f:
        return yaml.safe_load(f) or {}


def save_config(config: Dict[str, Any]):
    """
    Save configuration to file.

    Args:
        config: Dictionary of configuration values to save
    """
    _ensure_config_dir()

    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_config_value(key: str) -> Optional[str]:
    """
    Get a configuration value by key.

    Args:
        key: Configuration key to retrieve (supports both hyphen and underscore)

    Returns:
        Configuration value or None if not found
    """
    config = load_config()
    # Try both hyphenated and underscored versions
    value = config.get(key)
    if value is None:
        # Try alternative format (hyphen <-> underscore)
        alt_key = key.replace("-", "_") if "-" in key else key.replace("_", "-")
        value = config.get(alt_key)
    return value


def set_config_value(key: str, value: str):
    """
    Set a configuration value.

    Args:
        key: Configuration key to set
        value: Value to set
    """
    config = load_config()
    config[key] = value
    save_config(config)


def get_api_key() -> Optional[str]:
    """
    Get API key from config or environment variable.

    Returns:
        API key from config file, or LANGSMITH_API_KEY env var, or None
    """
    # Try config file first
    api_key = get_config_value("api_key")
    if api_key:
        return api_key

    # Fall back to environment variable
    return os.environ.get("LANGSMITH_API_KEY")


def get_base_url() -> Optional[str]:
    """
    Get base URL from config.

    Returns:
        Base URL from config file, or LANGSMITH_ENDPOINT env var, or None
    """
    if base_url := get_config_value("base_url"):
        return base_url
    return os.environ.get("LANGSMITH_ENDPOINT") or "https://api.smith.langchain.com"


def get_project_uuid() -> Optional[str]:
    """
    Get project UUID from config.

    Returns:
        Project UUID from config file or None
    """
    return get_config_value("project_uuid")


def get_default_format() -> str:
    """
    Get default output format from config.

    Returns:
        Output format ('raw', 'json', or 'pretty'), defaults to 'pretty'
    """
    return get_config_value("default_format") or "pretty"
