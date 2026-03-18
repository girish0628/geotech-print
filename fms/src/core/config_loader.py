"""Configuration loading utilities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from src.core.exceptions import ConfigLoadError


@dataclass(frozen=True)
class ConfigLoader:
    """
    Loads YAML application configuration.

    Parameters
    ----------
    config_path : str
        Path to YAML configuration file.
    """

    config_path: str

    def load(self) -> dict[str, Any]:
        """
        Read and parse the YAML config file.

        Returns
        -------
        dict[str, Any]
            Parsed configuration.

        Raises
        ------
        ConfigLoadError
            If the file cannot be read or parsed.
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                raise ConfigLoadError("Config root must be a YAML mapping.")
            return data
        except Exception as exc:
            raise ConfigLoadError(f"Failed to load config: {self.config_path}") from exc


def get_config_value(cfg: dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    """
    Retrieve a nested config value using a dotted key path.

    Parameters
    ----------
    cfg : dict[str, Any]
        Loaded configuration dictionary.
    dotted_key : str
        Dot-separated key path (e.g. "arcpy.workspace").
    default : Any
        Returned if the key path is not found.
    """
    cur: Any = cfg
    for part in dotted_key.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur
