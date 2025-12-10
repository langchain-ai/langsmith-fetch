"""Configuration file management for LangSmith Fetch."""

import os
from pathlib import Path
from typing import Any

import yaml

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
        key: Configuration key to set
        value: Value to set
    """
    config = load_config()
    config[key] = value
    save_config(config)


def _lookup_project_uuid_by_name(
    project_name: str,
    api_key: str,
    base_url: str | None = None
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
        ValueError: If no match, multiple matches, or lookup fails
    """
    from langsmith import Client

    # Initialize client
    client = Client(api_key=api_key, api_url=base_url)

    # Fetch projects
    try:
        projects = list(client.list_projects())
    except Exception as e:
        raise ValueError(
            f"Failed to fetch projects from LangSmith API: {e}\n"
            f"Consider setting LANGSMITH_PROJECT_UUID or using 'langsmith-fetch config set project-uuid <uuid>'."
        )

    # Find matching projects (case-insensitive partial match)
    matches = [
        p for p in projects
        if project_name.lower() in p.name.lower()
    ]

    if not matches:
        available = [p.name for p in projects[:5]]
        available_str = ', '.join(available) if available else 'none'
        raise ValueError(
            f"No project found matching '{project_name}'.\n"
            f"Available projects (first 5): {available_str}\n"
            f"Use 'langsmith-fetch config set project-uuid <uuid>' to set explicitly."
        )

    if len(matches) > 1:
        match_list = '\n'.join([f"  - {p.name} (UUID: {p.id})" for p in matches])
        raise ValueError(
            f"Multiple projects match '{project_name}':\n{match_list}\n"
            f"Use 'langsmith-fetch config set project-uuid <uuid>' to set explicitly."
        )

    return str(matches[0].id)


def get_api_key() -> str | None:
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


def get_base_url() -> str | None:
    """
    Get base URL from config.

    Returns:
        Base URL from config file, or LANGSMITH_ENDPOINT env var, or None
    """
    if base_url := get_config_value("base_url"):
        return base_url
    return os.environ.get("LANGSMITH_ENDPOINT") or "https://api.smith.langchain.com"


def get_project_uuid() -> str | None:
    """
    Get project UUID from config, env var, or by looking up LANGSMITH_PROJECT.

    Priority order:
    1. Config file (project_uuid)
    2. LANGSMITH_PROJECT_UUID env var (explicit UUID)
    3. LANGSMITH_PROJECT env var → API lookup → cached

    Returns:
        Project UUID from config file, env var, or looked up by name, or None
    """
    # Priority 1: Config file
    if config_uuid := get_config_value("project_uuid"):
        return config_uuid

    # Priority 2: Direct UUID from env var
    if env_uuid := os.environ.get("LANGSMITH_PROJECT_UUID"):
        return env_uuid

    # Priority 3: Project name from env var → lookup
    project_name = os.environ.get("LANGSMITH_PROJECT")
    if not project_name:
        return None

    # Check cache first
    if project_name in _project_uuid_cache:
        return _project_uuid_cache[project_name]

    # Lookup via API
    try:
        # Need API key for lookup
        api_key = get_api_key()
        if not api_key:
            import sys
            print(
                "Warning: LANGSMITH_PROJECT set but no API key found. "
                "Set LANGSMITH_API_KEY to enable project lookup.",
                file=sys.stderr
            )
            return None

        base_url = get_base_url()

        # Inform user about lookup
        import sys
        print(f"Looking up project '{project_name}'...", file=sys.stderr)

        uuid = _lookup_project_uuid_by_name(project_name, api_key, base_url)

        # Cache result
        _project_uuid_cache[project_name] = uuid

        print(f"Found project '{project_name}' (UUID: {uuid})", file=sys.stderr)

        return uuid

    except ValueError as e:
        import sys
        print(f"Error: {e}", file=sys.stderr)
        return None
    except Exception as e:
        import sys
        print(
            f"Warning: Failed to lookup project '{project_name}': {e}",
            file=sys.stderr
        )
        return None


def get_default_format() -> str:
    """
    Get default output format from config.

    Returns:
        Output format ('raw', 'json', or 'pretty'), defaults to 'pretty'
    """
    return get_config_value("default_format") or "pretty"
