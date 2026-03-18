"""Tests for config_loader module."""
import pytest
from src.core.config_loader import ConfigLoader, get_config_value


def test_load_valid_yaml(tmp_path):
    """Config file is loaded correctly."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("key:\n  nested: value\n")

    cfg = ConfigLoader(str(config_file)).load()

    assert cfg["key"]["nested"] == "value"


def test_get_config_value_dotted_key(tmp_path):
    """Dotted key access returns the correct value."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("arcpy:\n  workspace: C:/data/test.gdb\n")

    cfg = ConfigLoader(str(config_file)).load()
    result = get_config_value(cfg, "arcpy.workspace")

    assert result == "C:/data/test.gdb"


def test_get_config_value_missing_key_returns_default(tmp_path):
    """Missing key returns the supplied default."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("key: value\n")

    cfg = ConfigLoader(str(config_file)).load()
    result = get_config_value(cfg, "missing.key", default="fallback")

    assert result == "fallback"
