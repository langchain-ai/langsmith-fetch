"""Configuration file management for LangSmith Fetch."""

import os
from pathlib import Path
from typing import Any

import yaml

from .logging import logger

CONFIG_DIR = Path.home() / ".langsmith-cli"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

# Cache for project UUID lookups (avoids redundant API calls per session)
_project_uuid_cache: dict[str, str | None] = {}


def _ensure_config_dir():
    """Ensure the config directory exists."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """
    Load configuration from file.

    Returns:
        Dictionary of configuration values, empty dict if file doesn't exist
    """
    if not CONFIG_FILE.exists():
        return {}

    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f) or {}


def save_config(config: dict[str, Any]):
    """
    Save configuration to file.

    Args:
        config: Dictionary of configuration values to save
    """
    _ensure_config_dir()

    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_config_value(key: str) -> str | None:
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
        key: Configuration key to set (will be normalized to hyphen format)
        value: Value to set
    """
    config = load_config()

    # Normalize key to hyphen format
    normalized_key = key.replace("_", "-")
    config[normalized_key] = value

    # Clean up old underscore format if different from normalized
    if key != normalized_key and key in config:
        del config[key]

    save_config(config)

    # If manually setting project-uuid, clear in-memory cache
    # to force re-validation on next lookup
    if normalized_key == "project-uuid":
        _project_uuid_cache.clear()


def _update_project_config(project_name: str, project_uuid: str):
    """
    Update config file with both project name and UUID atomically.

    Args:
        project_name: Project name to store
        project_uuid: Project UUID to store
    """
    # Load, update both fields, and save atomically
    config = load_config()
    config["project-name"] = project_name
    config["project-uuid"] = project_uuid

    # Clean up old underscore format if it exists
    if "project_uuid" in config:
        del config["project_uuid"]
    if "project_name" in config:
        del config["project_name"]

    save_config(config)


def _lookup_project_uuid_by_name(
    project_name: str, api_key: str, base_url: str | None = None
) -> str:
    """
    Look up project UUID by name using LangSmith API.

    Args:
        project_name: Project name to search for
        api_key: LangSmith API key
        base_url: Optional base URL override

    Returns:
        Project UUID string

    Raises:
        ValueError: If project not found or lookup fails
    """
    from langsmith import Client

    # Initialize client
    client = Client(api_key=api_key, api_url=base_url)

    # Try direct lookup by project name
    try:
        project = client.read_project(project_name=project_name)
        return str(project.id)
    except Exception as e:
        raise ValueError(
            f"Project '{project_name}' not found: {e}\n"
            f"Use 'langsmith-fetch config set project-uuid <uuid>' to set explicitly, "
            f"or set LANGSMITH_PROJECT_UUID env var."
        ) from e


def get_api_key() -> str | None:
    """
    Get API key from environment variable or config.

    Returns:
        API key from LANGSMITH_API_KEY env var, or config file, or None
    """
    return os.environ.get("LANGSMITH_API_KEY") or get_config_value("api_key")


def get_base_url() -> str:
    """
    Get base URL from environment variable or config.

    Returns:
        Base URL from LANGSMITH_ENDPOINT env var, or config file, or default
    """
    return (
        os.environ.get("LANGSMITH_ENDPOINT")
        or get_config_value("base_url")
        or "https://api.smith.langchain.com"
    )


def get_project_uuid() -> str | None:
    """
    Get project UUID with automatic sync detection.

    Priority order:
    1. LANGSMITH_PROJECT_UUID env var (explicit UUID override)
    2. LANGSMITH_PROJECT env var → check if config matches → fetch if stale
    3. Config file as fallback (when no env var set)

    Returns:
        Project UUID or None
    """
    env_uuid = os.environ.get("LANGSMITH_PROJECT_UUID")
    if env_uuid:
        return env_uuid

    env_project_name = os.environ.get("LANGSMITH_PROJECT")

    config_project_uuid = get_config_value("project-uuid")
    config_project_name = get_config_value("project-name")

    if not env_project_name:
        if config_project_uuid:
            return config_project_uuid
        return None

    if env_project_name in _project_uuid_cache:
        cached_uuid = _project_uuid_cache[env_project_name]
        if cached_uuid and config_project_name != env_project_name:
            _update_project_config(env_project_name, cached_uuid)
        return cached_uuid

    if config_project_name == env_project_name and config_project_uuid:
        _project_uuid_cache[env_project_name] = config_project_uuid
        return config_project_uuid

    logger.info(f"Project name changed to '{env_project_name}', fetching UUID...")

    api_key = get_api_key()
    if not api_key:
        logger.warning(
            "LANGSMITH_PROJECT set but no API key found. Set LANGSMITH_API_KEY to enable project lookup."
        )
        return None

    base_url = get_base_url()

    try:
        uuid = _lookup_project_uuid_by_name(env_project_name, api_key, base_url)

        _project_uuid_cache[env_project_name] = uuid

        _update_project_config(env_project_name, uuid)

        logger.info(f"Found project '{env_project_name}' (UUID: {uuid})")

        return uuid

    except ValueError as e:
        logger.error(str(e))
        return None
    except Exception as e:
        logger.warning(f"Failed to lookup project '{env_project_name}': {e}")
        return None


def get_default_format() -> str:
    """
    Get default output format from environment variable or config.

    Returns:
        Output format ('raw', 'json', or 'pretty'), defaults to 'pretty'
    """
    return (
        os.environ.get("LANGSMITH_DEFAULT_FORMAT")
        or get_config_value("default_format")
        or "pretty"
    )
