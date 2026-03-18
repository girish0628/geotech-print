@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo   Python GIS Automation Project Creator
echo   Template: ArcPy + FME Flow + Jenkins CI/CD
echo ============================================================
echo.

set /p PROJECT_NAME=Enter project name (e.g. python-roads-automation):

if "%PROJECT_NAME%"=="" (
    echo ERROR: Project name cannot be empty.
    exit /b 1
)

if exist "%PROJECT_NAME%" (
    echo ERROR: Folder "%PROJECT_NAME%" already exists. Choose a different name.
    exit /b 1
)

echo.
echo Creating project: %PROJECT_NAME%
echo.

REM ==============================
REM Create Root Folder
REM ==============================
mkdir "%PROJECT_NAME%"
cd "%PROJECT_NAME%"

REM ==============================
REM Directory Structure
REM ==============================
echo [1/9] Creating directory structure...
mkdir src\core
mkdir src\services
mkdir src\runners
mkdir src\utils
mkdir config
mkdir tests\test_core
mkdir tests\test_services
mkdir logs
mkdir docs

REM ==============================
REM Package Init Files
REM ==============================
echo [2/9] Creating package files...
type nul > src\__init__.py
type nul > src\core\__init__.py
type nul > src\services\__init__.py
type nul > src\runners\__init__.py
type nul > src\utils\__init__.py
type nul > tests\__init__.py
type nul > tests\test_core\__init__.py
type nul > tests\test_services\__init__.py
type nul > logs\.gitkeep

REM ==============================
REM Core: exceptions.py
REM ==============================
echo [3/9] Creating core framework files...

(
echo """Custom exceptions for the application."""
echo.
echo.
echo class ConfigLoadError^(Exception^):
echo     """Raised when configuration loading fails."""
echo.
echo.
echo class ArcPyExecutionError^(Exception^):
echo     """Raised when an ArcPy operation fails."""
echo.
echo.
echo class FMEWebhookError^(Exception^):
echo     """Raised when an FME Flow webhook call fails."""
echo.
echo.
echo class ValidationError^(Exception^):
echo     """Raised when input validation fails."""
) > src\core\exceptions.py


REM ==============================
REM Core: logger.py
REM ==============================
(
echo """Logging configuration and utilities."""
echo from __future__ import annotations
echo.
echo import logging
echo import logging.config
echo from typing import Any
echo.
echo import yaml
echo.
echo.
echo def setup_logging^(logging_config_path: str^) -^> None:
echo     """
echo     Initialize logging using a YAML config file.
echo.
echo     Parameters
echo     ----------
echo     logging_config_path : str
echo         Path to the logging YAML configuration.
echo     """
echo     with open^(logging_config_path, "r", encoding="utf-8"^) as f:
echo         cfg: dict[str, Any] = yaml.safe_load^(f^) or {}
echo     logging.config.dictConfig^(cfg^)
echo.
echo.
echo def get_logger^(name: str^) -^> logging.Logger:
echo     """
echo     Return a named logger.
echo.
echo     Parameters
echo     ----------
echo     name : str
echo         Logger name, typically __name__.
echo     """
echo     return logging.getLogger^(name^)
) > src\core\logger.py


REM ==============================
REM Core: config_loader.py
REM ==============================
(
echo """Configuration loading utilities."""
echo from __future__ import annotations
echo.
echo from dataclasses import dataclass
echo from typing import Any
echo.
echo import yaml
echo.
echo from src.core.exceptions import ConfigLoadError
echo.
echo.
echo @dataclass^(frozen=True^)
echo class ConfigLoader:
echo     """
echo     Loads YAML application configuration.
echo.
echo     Parameters
echo     ----------
echo     config_path : str
echo         Path to YAML configuration file.
echo     """
echo.
echo     config_path: str
echo.
echo     def load^(self^) -^> dict[str, Any]:
echo         """
echo         Read and parse the YAML config file.
echo.
echo         Returns
echo         -------
echo         dict[str, Any]
echo             Parsed configuration.
echo.
echo         Raises
echo         ------
echo         ConfigLoadError
echo             If the file cannot be read or parsed.
echo         """
echo         try:
echo             with open^(self.config_path, "r", encoding="utf-8"^) as f:
echo                 data = yaml.safe_load^(f^) or {}
echo             if not isinstance^(data, dict^):
echo                 raise ConfigLoadError^("Config root must be a YAML mapping."^)
echo             return data
echo         except Exception as exc:
echo             raise ConfigLoadError^(f"Failed to load config: {self.config_path}"^) from exc
echo.
echo.
echo def get_config_value^(cfg: dict[str, Any], dotted_key: str, default: Any = None^) -^> Any:
echo     """
echo     Retrieve a nested config value using a dotted key path.
echo.
echo     Parameters
echo     ----------
echo     cfg : dict[str, Any]
echo         Loaded configuration dictionary.
echo     dotted_key : str
echo         Dot-separated key path ^(e.g. "arcpy.workspace"^).
echo     default : Any
echo         Returned if the key path is not found.
echo     """
echo     cur: Any = cfg
echo     for part in dotted_key.split^("."^):
echo         if not isinstance^(cur, dict^) or part not in cur:
echo             return default
echo         cur = cur[part]
echo     return cur
) > src\core\config_loader.py


REM ==============================
REM Service: arcpy_service.py
REM ==============================
echo [4/9] Creating service files...

(
echo """ArcPy service for GIS geodatabase operations."""
echo from __future__ import annotations
echo.
echo from typing import Any
echo.
echo from src.core.exceptions import ArcPyExecutionError
echo from src.core.logger import get_logger
echo.
echo logger = get_logger^(__name__^)
echo.
echo.
echo class ArcPyService:
echo     """
echo     Handles ArcPy geodatabase operations.
echo.
echo     Notes
echo     -----
echo     ArcPy is imported lazily so unit tests run without ArcGIS Pro installed.
echo     Always run this service from the ArcGIS Pro cloned conda environment.
echo.
echo     Parameters
echo     ----------
echo     workspace : str
echo         Geodatabase workspace path ^(file GDB path or SDE connection string^).
echo     """
echo.
echo     def __init__^(self, workspace: str^) -^> None:
echo         self.workspace = workspace
echo.
echo     def _arcpy^(self^):
echo         """Lazy import ArcPy. Only available in ArcGIS Pro Python environment."""
echo         import arcpy  # type: ignore
echo         return arcpy
echo.
echo     def add_fields^(self, feature_class: str, fields: list[dict[str, Any]]^) -^> None:
echo         """
echo         Add multiple fields to a feature class using config-driven definitions.
echo.
echo         Parameters
echo         ----------
echo         feature_class : str
echo             Feature class name or full path.
echo         fields : list[dict[str, Any]]
echo             Field definitions, e.g.:
echo             [{"name": "MY_FIELD", "type": "TEXT", "length": 100}]
echo.
echo         Raises
echo         ------
echo         ArcPyExecutionError
echo             If any field addition fails.
echo         """
echo         try:
echo             arcpy = self._arcpy^(^)
echo             arcpy.env.workspace = self.workspace
echo             for f in fields:
echo                 name = f["name"]
echo                 ftype = f["type"]
echo                 length = f.get^("length"^)
echo                 kwargs: dict[str, Any] = {
echo                     "in_table": feature_class,
echo                     "field_name": name,
echo                     "field_type": ftype,
echo                 }
echo                 if length is not None:
echo                     kwargs["field_length"] = length
echo                 logger.info^("Adding field '%%s' ^(%%s^) to '%%s'", name, ftype, feature_class^)
echo                 arcpy.AddField_management^(**kwargs^)
echo         except Exception as exc:
echo             logger.error^("add_fields failed for '%%s'", feature_class, exc_info=True^)
echo             raise ArcPyExecutionError^("Failed to add fields to feature class"^) from exc
echo.
echo     def calculate_field^(
echo         self, feature_class: str, field_name: str, expression: str
echo     ^) -^> None:
echo         """
echo         Calculate field values using a Python 3 expression.
echo.
echo         Parameters
echo         ----------
echo         feature_class : str
echo             Feature class name or full path.
echo         field_name : str
echo             Name of the field to calculate.
echo         expression : str
echo             ArcPy Python 3 field calculator expression.
echo.
echo         Raises
echo         ------
echo         ArcPyExecutionError
echo             If the calculation fails.
echo         """
echo         try:
echo             arcpy = self._arcpy^(^)
echo             arcpy.env.workspace = self.workspace
echo             logger.info^("Calculating field '%%s' on '%%s'", field_name, feature_class^)
echo             arcpy.CalculateField_management^(
echo                 in_table=feature_class,
echo                 field=field_name,
echo                 expression=expression,
echo                 expression_type="PYTHON3",
echo             ^)
echo         except Exception as exc:
echo             logger.error^("calculate_field failed for '%%s'", field_name, exc_info=True^)
echo             raise ArcPyExecutionError^("Failed to calculate field"^) from exc
echo.
echo     def copy_features^(self, source: str, destination: str^) -^> None:
echo         """
echo         Copy a feature class to a new location within the workspace.
echo.
echo         Parameters
echo         ----------
echo         source : str
echo             Source feature class name or path.
echo         destination : str
echo             Destination feature class name or path.
echo.
echo         Raises
echo         ------
echo         ArcPyExecutionError
echo             If the copy operation fails.
echo         """
echo         try:
echo             arcpy = self._arcpy^(^)
echo             arcpy.env.workspace = self.workspace
echo             logger.info^("Copying '%%s' to '%%s'", source, destination^)
echo             arcpy.CopyFeatures_management^(
echo                 in_features=source,
echo                 out_feature_class=destination,
echo             ^)
echo         except Exception as exc:
echo             logger.error^("copy_features failed", exc_info=True^)
echo             raise ArcPyExecutionError^("Failed to copy features"^) from exc
) > src\services\arcpy_service.py


REM ==============================
REM Service: fme_webhook_service.py
REM ==============================
(
echo """FME Flow webhook service."""
echo from __future__ import annotations
echo.
echo from typing import Any
echo.
echo import requests
echo.
echo from src.core.exceptions import FMEWebhookError
echo from src.core.logger import get_logger
echo.
echo logger = get_logger^(__name__^)
echo.
echo.
echo class FMEWebhookService:
echo     """
echo     Sends payloads to FME Flow via webhook endpoint.
echo.
echo     Parameters
echo     ----------
echo     webhook_url : str
echo         Target FME Flow webhook URL.
echo     timeout_s : int
echo         Request timeout in seconds.
echo     """
echo.
echo     def __init__^(self, webhook_url: str, timeout_s: int = 60^) -^> None:
echo         self.webhook_url = webhook_url
echo         self.timeout_s = timeout_s
echo.
echo     def trigger^(self, payload: dict[str, Any]^) -^> dict[str, Any]:
echo         """
echo         Trigger the FME Flow webhook.
echo.
echo         Parameters
echo         ----------
echo         payload : dict[str, Any]
echo             JSON payload to send.
echo.
echo         Returns
echo         -------
echo         dict[str, Any]
echo             Parsed JSON response or status dict.
echo.
echo         Raises
echo         ------
echo         FMEWebhookError
echo             If the request fails or returns a non-2xx status.
echo         """
echo         try:
echo             logger.info^("Calling FME webhook: %%s", self.webhook_url^)
echo             resp = requests.post^(self.webhook_url, json=payload, timeout=self.timeout_s^)
echo             resp.raise_for_status^(^)
echo             if resp.headers.get^("content-type", ""^).lower^(^).startswith^("application/json"^):
echo                 return resp.json^(^)
echo             return {"status_code": resp.status_code, "text": resp.text}
echo         except requests.RequestException as exc:
echo             logger.error^("FME webhook request failed: %%s", exc, exc_info=True^)
echo             raise FMEWebhookError^("FME webhook call failed"^) from exc
) > src\services\fme_webhook_service.py


REM ==============================
REM Runner: main_runner.py
REM ==============================
echo [5/9] Creating runner...

(
echo """Main runner for GIS automation workflow."""
echo from __future__ import annotations
echo.
echo import argparse
echo import sys
echo from typing import Any
echo.
echo from src.core.config_loader import ConfigLoader, get_config_value
echo from src.core.logger import setup_logging, get_logger
echo from src.services.arcpy_service import ArcPyService
echo from src.services.fme_webhook_service import FMEWebhookService
echo.
echo.
echo def parse_args^(^) -^> argparse.Namespace:
echo     """Parse CLI arguments."""
echo     parser = argparse.ArgumentParser^(description="GIS Automation Runner"^)
echo     parser.add_argument^("--config", required=True, help="Path to app config YAML"^)
echo     parser.add_argument^("--logging", required=True, help="Path to logging config YAML"^)
echo     parser.add_argument^("--env", default="DEV", help="Environment ^(DEV/UAT/PROD^)"^)
echo     return parser.parse_args^(^)
echo.
echo.
echo def run^(cfg: dict[str, Any]^) -^> None:
echo     """
echo     Execute workflow steps in order.
echo.
echo     Parameters
echo     ----------
echo     cfg : dict[str, Any]
echo         Loaded application configuration.
echo     """
echo     logger = get_logger^(__name__^)
echo     logger.info^("=" * 60^)
echo     logger.info^("GIS Automation Workflow Started"^)
echo     logger.info^("=" * 60^)
echo.
echo     # --- ArcPy Step ---
echo     workspace = get_config_value^(cfg, "arcpy.workspace"^)
echo     feature_class = get_config_value^(cfg, "arcpy.feature_class"^)
echo     fields = get_config_value^(cfg, "arcpy.fields", default=[]^)
echo.
echo     if workspace and feature_class and fields:
echo         ArcPyService^(workspace=workspace^).add_fields^(
echo             feature_class=feature_class, fields=fields
echo         ^)
echo         logger.info^("ArcPy step complete"^)
echo     else:
echo         logger.warning^("Skipping ArcPy step: missing arcpy config keys"^)
echo.
echo     # --- FME Step ---
echo     fme_url = get_config_value^(cfg, "fme.webhook_url"^)
echo     timeout = int^(get_config_value^(cfg, "fme.timeout", default=60^)^)
echo.
echo     if fme_url:
echo         resp = FMEWebhookService^(webhook_url=fme_url, timeout_s=timeout^).trigger^(
echo             payload={"status": "FIELDS_ADDED", "featureClass": feature_class}
echo         ^)
echo         logger.info^("FME step complete: response=%%s", resp^)
echo     else:
echo         logger.warning^("Skipping FME step: missing fme.webhook_url in config"^)
echo.
echo     logger.info^("=" * 60^)
echo     logger.info^("GIS Automation Workflow Completed"^)
echo     logger.info^("=" * 60^)
echo.
echo.
echo def main^(^) -^> None:
echo     """Main entry point."""
echo     try:
echo         args = parse_args^(^)
echo         setup_logging^(args.logging^)
echo         logger = get_logger^(__name__^)
echo         logger.info^("Environment: %%s", args.env^)
echo         cfg = ConfigLoader^(args.config^).load^(^)
echo         run^(cfg^)
echo     except Exception:
echo         get_logger^(__name__^).error^("Workflow failed", exc_info=True^)
echo         sys.exit^(1^)
echo.
echo.
echo if __name__ == "__main__":
echo     main^(^)
) > src\runners\main_runner.py


REM ==============================
REM Configuration Files
REM ==============================
echo [6/9] Creating configuration files...

(
echo # Application Configuration
echo # -------------------------------------------------------
echo # Update all values below before running.
echo # NEVER hardcode paths, credentials, or URLs in .py files.
echo # -------------------------------------------------------
echo environment: DEV
echo.
echo # ArcPy / Geodatabase settings
echo arcpy:
echo   workspace: "C:/GISData/project.gdb"
echo   feature_class: "ROADS"
echo   fields:
echo     - name: ROAD_WIDTH
echo       type: DOUBLE
echo     - name: SURFACE_TYPE
echo       type: TEXT
echo       length: 50
echo.
echo # FME Flow webhook settings
echo fme:
echo   webhook_url: "https://fme.company.com/fmeserver/webhooks/workflow"
echo   timeout: 60
) > config\app_config.yaml


(
echo version: 1
echo disable_existing_loggers: false
echo.
echo formatters:
echo   standard:
echo     format: "%%(asctime)s ^| %%(levelname)-8s ^| %%(name)s ^| %%(message)s"
echo   detailed:
echo     format: "%%(asctime)s ^| %%(levelname)-8s ^| %%(name)s ^| %%(funcName)s:%%(lineno)d ^| %%(message)s"
echo.
echo handlers:
echo   console:
echo     class: logging.StreamHandler
echo     level: INFO
echo     formatter: standard
echo     stream: ext://sys.stdout
echo.
echo   file:
echo     class: logging.handlers.RotatingFileHandler
echo     level: DEBUG
echo     formatter: detailed
echo     filename: logs/app.log
echo     maxBytes: 10485760
echo     backupCount: 5
echo     encoding: utf-8
echo.
echo root:
echo   level: DEBUG
echo   handlers: [console, file]
) > config\logging.yaml


(
echo version: 1
echo disable_existing_loggers: false
echo.
echo formatters:
echo   standard:
echo     format: "%%(asctime)s ^| %%(levelname)-8s ^| %%(name)s ^| %%(message)s"
echo.
echo handlers:
echo   console:
echo     class: logging.StreamHandler
echo     level: INFO
echo     formatter: standard
echo     stream: ext://sys.stdout
echo.
echo   file:
echo     class: logging.handlers.RotatingFileHandler
echo     level: INFO
echo     formatter: standard
echo     filename: logs/production.log
echo     maxBytes: 10485760
echo     backupCount: 10
echo     encoding: utf-8
echo.
echo root:
echo   level: INFO
echo   handlers: [console, file]
) > config\logging.prod.yaml


REM ==============================
REM Tests
REM ==============================
echo [7/9] Creating test files...

(
echo """Shared pytest fixtures."""
echo import pytest
) > tests\conftest.py


(
echo """Tests for config_loader module."""
echo import pytest
echo from src.core.config_loader import ConfigLoader, get_config_value
echo.
echo.
echo def test_load_valid_yaml^(tmp_path^):
echo     """Config file is loaded correctly."""
echo     config_file = tmp_path / "test_config.yaml"
echo     config_file.write_text^("key:\n  nested: value\n"^)
echo.
echo     cfg = ConfigLoader^(str^(config_file^)^).load^(^)
echo.
echo     assert cfg["key"]["nested"] == "value"
echo.
echo.
echo def test_get_config_value_dotted_key^(tmp_path^):
echo     """Dotted key access returns the correct value."""
echo     config_file = tmp_path / "test_config.yaml"
echo     config_file.write_text^("arcpy:\n  workspace: C:/data/test.gdb\n"^)
echo.
echo     cfg = ConfigLoader^(str^(config_file^)^).load^(^)
echo     result = get_config_value^(cfg, "arcpy.workspace"^)
echo.
echo     assert result == "C:/data/test.gdb"
echo.
echo.
echo def test_get_config_value_missing_key_returns_default^(tmp_path^):
echo     """Missing key returns the supplied default."""
echo     config_file = tmp_path / "test_config.yaml"
echo     config_file.write_text^("key: value\n"^)
echo.
echo     cfg = ConfigLoader^(str^(config_file^)^).load^(^)
echo     result = get_config_value^(cfg, "missing.key", default="fallback"^)
echo.
echo     assert result == "fallback"
) > tests\test_core\test_config_loader.py


(
echo """Tests for ArcPyService."""
echo import pytest
echo from src.services.arcpy_service import ArcPyService
echo from src.core.exceptions import ArcPyExecutionError
echo.
echo.
echo class FakeArcPy:
echo     """Minimal ArcPy stand-in for unit tests."""
echo.
echo     class env:
echo         workspace = None
echo.
echo     added_fields: list = []
echo     calculated_fields: list = []
echo     copied_features: list = []
echo.
echo     @classmethod
echo     def AddField_management^(cls, **kwargs^):
echo         cls.added_fields.append^(kwargs^)
echo.
echo     @classmethod
echo     def CalculateField_management^(cls, **kwargs^):
echo         cls.calculated_fields.append^(kwargs^)
echo.
echo     @classmethod
echo     def CopyFeatures_management^(cls, **kwargs^):
echo         cls.copied_features.append^(kwargs^)
echo.
echo.
echo def test_add_fields_success^(monkeypatch^):
echo     """add_fields calls AddField_management for each field."""
echo     fake = FakeArcPy^(^)
echo     fake.added_fields = []
echo     svc = ArcPyService^(workspace="C:/test.gdb"^)
echo     monkeypatch.setattr^(svc, "_arcpy", lambda: fake^)
echo.
echo     fields = [
echo         {"name": "ROAD_WIDTH", "type": "DOUBLE"},
echo         {"name": "SURFACE_TYPE", "type": "TEXT", "length": 50},
echo     ]
echo     svc.add_fields^("ROADS", fields^)
echo.
echo     assert len^(fake.added_fields^) == 2
echo     assert fake.added_fields[0]["field_name"] == "ROAD_WIDTH"
echo     assert "field_length" not in fake.added_fields[0]
echo     assert fake.added_fields[1]["field_length"] == 50
echo.
echo.
echo def test_add_fields_raises_on_arcpy_failure^(monkeypatch^):
echo     """add_fields raises ArcPyExecutionError when ArcPy fails."""
echo.
echo     class BrokenArcPy:
echo         class env:
echo             workspace = None
echo.
echo         def AddField_management^(self, **kwargs^):
echo             raise RuntimeError^("simulated ArcPy error"^)
echo.
echo     svc = ArcPyService^(workspace="C:/test.gdb"^)
echo     monkeypatch.setattr^(svc, "_arcpy", lambda: BrokenArcPy^(^)^)
echo.
echo     with pytest.raises^(ArcPyExecutionError^):
echo         svc.add_fields^("ROADS", [{"name": "F", "type": "TEXT"}]^)
echo.
echo.
echo def test_calculate_field_success^(monkeypatch^):
echo     """calculate_field calls CalculateField_management."""
echo     fake = FakeArcPy^(^)
echo     fake.calculated_fields = []
echo     svc = ArcPyService^(workspace="C:/test.gdb"^)
echo     monkeypatch.setattr^(svc, "_arcpy", lambda: fake^)
echo.
echo     svc.calculate_field^("ROADS", "ROAD_WIDTH", "100"^)
echo.
echo     assert len^(fake.calculated_fields^) == 1
echo     assert fake.calculated_fields[0]["field"] == "ROAD_WIDTH"
echo     assert fake.calculated_fields[0]["expression"] == "100"
) > tests\test_services\test_arcpy_service.py


(
echo """Tests for FMEWebhookService."""
echo import pytest
echo import requests
echo from src.services.fme_webhook_service import FMEWebhookService
echo from src.core.exceptions import FMEWebhookError
echo.
echo.
echo class FakeResponse:
echo     status_code = 200
echo     text = "ok"
echo.
echo     def raise_for_status^(self^):
echo         pass
echo.
echo     @property
echo     def headers^(self^):
echo         return {"content-type": "application/json"}
echo.
echo     def json^(self^):
echo         return {"status": "SUCCESS"}
echo.
echo.
echo def test_trigger_success^(monkeypatch^):
echo     """trigger^(^) returns parsed JSON on success."""
echo     monkeypatch.setattr^(requests, "post", lambda *a, **kw: FakeResponse^(^)^)
echo.
echo     svc = FMEWebhookService^(webhook_url="https://fme.test/webhook", timeout_s=10^)
echo     result = svc.trigger^(payload={"key": "value"}^)
echo.
echo     assert result["status"] == "SUCCESS"
echo.
echo.
echo def test_trigger_raises_on_network_error^(monkeypatch^):
echo     """trigger^(^) raises FMEWebhookError on network failure."""
echo.
echo     def fail^(*a, **kw^):
echo         raise requests.RequestException^("connection error"^)
echo.
echo     monkeypatch.setattr^(requests, "post", fail^)
echo.
echo     svc = FMEWebhookService^(webhook_url="https://fme.test/webhook", timeout_s=10^)
echo     with pytest.raises^(FMEWebhookError^):
echo         svc.trigger^(payload={}^)
) > tests\test_services\test_fme_webhook_service.py


REM ==============================
REM requirements.txt
REM ==============================
echo [8/9] Creating project config files...

(
echo # Core dependencies
echo # ---------------------------------------------------------
echo # NOTE: ArcPy is provided by ArcGIS Pro — do NOT install
echo # it via pip. Run this project from the ArcGIS Pro cloned
echo # conda environment. See README.md for setup instructions.
echo # ---------------------------------------------------------
echo pyyaml^>=6.0.1
echo requests^>=2.32.0
) > requirements.txt


(
echo # Include all production dependencies
echo -r requirements.txt
echo.
echo # Development and testing tools
echo pytest^>=8.0.0
echo pytest-cov^>=4.1.0
echo ruff^>=0.4.0
echo pre-commit^>=3.0.0
) > requirements.dev.txt


REM ==============================
REM pyproject.toml
REM ==============================
(
echo [tool.pytest.ini_options]
echo testpaths = ["tests"]
echo addopts = "-v"
echo markers = [
echo     "integration: marks tests requiring real external systems ^(ArcGIS Pro, FME Flow^)",
echo ]
echo.
echo [tool.ruff]
echo line-length = 120
echo target-version = "py311"
echo.
echo [tool.ruff.lint]
echo select = ["E", "F", "I", "N", "W"]
echo ignore = ["E501"]
) > pyproject.toml


REM ==============================
REM .pre-commit-config.yaml
REM ==============================
(
echo repos:
echo   - repo: https://github.com/astral-sh/ruff-pre-commit
echo     rev: v0.4.4
echo     hooks:
echo       - id: ruff
echo         args: [--fix]
echo       - id: ruff-format
echo.
echo   - repo: https://github.com/pre-commit/pre-commit-hooks
echo     rev: v4.5.0
echo     hooks:
echo       - id: end-of-file-fixer
echo       - id: trailing-whitespace
echo       - id: check-yaml
echo       - id: check-added-large-files
echo.
echo   - repo: local
echo     hooks:
echo       - id: pytest
echo         name: pytest
echo         entry: pytest
echo         language: system
echo         pass_filenames: false
echo         always_run: true
) > .pre-commit-config.yaml


REM ==============================
REM .gitlab-ci.yml
REM ==============================
(
echo # GitLab CI/CD Pipeline
echo # ArcPy is mocked in unit tests so the pipeline runs without ArcGIS Pro.
echo default:
echo   image: python:3.11
echo   before_script:
echo     - pip install -r requirements.dev.txt
echo.
echo stages:
echo   - lint
echo   - test
echo.
echo lint:
echo   stage: lint
echo   script:
echo     - ruff check src/ tests/
echo.
echo test:
echo   stage: test
echo   script:
echo     - pytest tests/ -v --junitxml=test-results.xml
echo   artifacts:
echo     reports:
echo       junit: test-results.xml
echo     expire_in: 1 week
) > .gitlab-ci.yml


REM ==============================
REM Jenkinsfile
REM ==============================
(
echo pipeline {
echo     // Run on a Jenkins node with ArcGIS Pro installed.
echo     agent { label 'arcgis-pro' }
echo.
echo     parameters {
echo         choice^(
echo             name: 'ENV',
echo             choices: ['DEV', 'UAT', 'PROD'],
echo             description: 'Target environment'
echo         ^)
echo         string^(
echo             name: 'ARCGIS_PYTHON',
echo             defaultValue: 'C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe',
echo             description: 'ArcGIS Pro Python executable path. Use a cloned conda env path in production.'
echo         ^)
echo         string^(
echo             name: 'CONFIG_PATH',
echo             defaultValue: 'config/app_config.yaml',
echo             description: 'Path to app config YAML'
echo         ^)
echo         string^(
echo             name: 'LOGGING_PATH',
echo             defaultValue: 'config/logging.prod.yaml',
echo             description: 'Path to logging config YAML'
echo         ^)
echo     }
echo.
echo     stages {
echo         stage^('Setup'^) {
echo             steps {
echo                 bat "\"${params.ARCGIS_PYTHON}\" -m pip install --upgrade pip"
echo                 bat "\"${params.ARCGIS_PYTHON}\" -m pip install -r requirements.txt"
echo             }
echo         }
echo.
echo         stage^('Lint'^) {
echo             steps {
echo                 bat "\"${params.ARCGIS_PYTHON}\" -m ruff check src/ tests/"
echo             }
echo         }
echo.
echo         stage^('Test'^) {
echo             steps {
echo                 bat "\"${params.ARCGIS_PYTHON}\" -m pytest tests/ -v --junitxml=test-results.xml"
echo             }
echo             post {
echo                 always {
echo                     junit allowEmptyResults: true, testResults: 'test-results.xml'
echo                 }
echo             }
echo         }
echo.
echo         stage^('Run'^) {
echo             steps {
echo                 bat "\"${params.ARCGIS_PYTHON}\" -m src.runners.main_runner --config ${params.CONFIG_PATH} --logging ${params.LOGGING_PATH} --env ${params.ENV}"
echo             }
echo         }
echo     }
echo.
echo     post {
echo         always {
echo             archiveArtifacts artifacts: 'logs/*.log', allowEmptyArchive: true
echo         }
echo         success {
echo             echo 'Workflow completed successfully.'
echo         }
echo         failure {
echo             echo 'Workflow failed. Check archived logs for details.'
echo         }
echo     }
echo }
) > Jenkinsfile


REM ==============================
REM .gitignore
REM ==============================
(
echo # Python
echo __pycache__/
echo *.py[cod]
echo *$py.class
echo *.so
echo *.egg
echo *.egg-info/
echo dist/
echo build/
echo.
echo # Virtual environments
echo venv/
echo env/
echo ENV/
echo .venv/
echo virtualenv/
echo.
echo # Logs
echo logs/*.log
echo logs/*.log.*
echo.
echo # IDE
echo .vscode/
echo .idea/
echo *.swp
echo *.swo
echo.
echo # OS
echo .DS_Store
echo Thumbs.db
echo desktop.ini
echo.
echo # Secrets ^(never commit these^)
echo config/secrets.yaml
echo config/secrets.*.yaml
echo .env
echo *.env
echo.
echo # Testing
echo .pytest_cache/
echo .coverage
echo htmlcov/
echo .tox/
echo.
echo # ArcGIS lock files
echo *.lock
echo *.gdb-journal
echo.
echo # Temporary files
echo *.tmp
echo *.bak
echo *~
echo .cache/
) > .gitignore


REM ==============================
REM README.md
REM ==============================
echo [9/9] Creating README...

(
echo # %PROJECT_NAME%
echo.
echo Python GIS automation project using ArcPy, FME Flow, and Jenkins CI/CD.
echo.
echo ## Python Environment Setup ^(Required for ArcPy^)
echo.
echo ArcPy is **only available inside the ArcGIS Pro Python environment**.
echo A plain `python -m venv` will NOT have access to ArcPy.
echo.
echo ### Recommended: Clone the ArcGIS Pro conda environment
echo.
echo **Step 1 — Open ArcGIS Pro Python Command Prompt**
echo Start Menu ^> ArcGIS ^> Python Command Prompt
echo.
echo **Step 2 — Clone the default environment**
echo Never modify the base `arcgispro-py3` environment directly.
echo ```
echo conda create --name %PROJECT_NAME%-env --clone arcgispro-py3
echo conda activate %PROJECT_NAME%-env
echo ```
echo.
echo **Step 3 — Install project dependencies**
echo ```
echo pip install -r requirements.dev.txt
echo ```
echo.
echo **Step 4 — Verify ArcPy is available**
echo ```
echo python -c "import arcpy; print^(arcpy.GetInstallInfo^(^)['Version']^)"
echo ```
echo.
echo **Step 5 — Install pre-commit hooks**
echo ```
echo pre-commit install
echo ```
echo.
echo ### Jenkins: Point to the cloned conda env
echo.
echo Use the cloned environment's Python executable in Jenkins:
echo - User installs: `C:\Users\{username}\AppData\Local\ESRI\conda\envs\%PROJECT_NAME%-env\python.exe`
echo - Service account: `C:\ProgramData\ESRI\conda\envs\%PROJECT_NAME%-env\python.exe`
echo.
echo Configure this path in the Jenkins job parameter `ARCGIS_PYTHON`.
echo.
echo ## Project Structure
echo.
echo ```
echo %PROJECT_NAME%/
echo ^|-- src/
echo ^|   ^|-- core/              # Config loading, logging, custom exceptions
echo ^|   ^|-- services/          # Business logic ^(one file per external system^)
echo ^|   ^|   ^|-- arcpy_service.py      # ArcPy geodatabase operations
echo ^|   ^|   ^`-- fme_webhook_service.py # FME Flow webhook calls
echo ^|   ^|-- runners/           # Entry points called by Jenkins / CLI
echo ^|   ^|   ^`-- main_runner.py
echo ^|   ^`-- utils/             # Shared helpers ^(add as needed^)
echo ^|-- config/
echo ^|   ^|-- app_config.yaml    # All runtime values ^(edit before running^)
echo ^|   ^|-- logging.yaml       # Dev logging ^(console + file, DEBUG^)
echo ^|   ^`-- logging.prod.yaml  # Prod logging ^(console + file, INFO^)
echo ^|-- tests/
echo ^|   ^|-- test_core/
echo ^|   ^`-- test_services/
echo ^|-- logs/                  # Log output ^(git-ignored^)
echo ^|-- Jenkinsfile
echo ^`-- README.md
echo ```
echo.
echo ## Run Locally
echo.
echo ```
echo conda activate %PROJECT_NAME%-env
echo python -m src.runners.main_runner --config config/app_config.yaml --logging config/logging.yaml --env DEV
echo ```
echo.
echo ## Run Tests
echo.
echo ```
echo pytest tests/ -v
echo ```
echo.
echo ## Run Linting
echo.
echo ```
echo ruff check src/ tests/
echo ```
echo.
echo ## Configuration
echo.
echo Edit `config/app_config.yaml` before running. All paths and URLs must be real values.
echo No hardcoded values are allowed in `.py` files.
echo.
echo ## Adding a New Service
echo.
echo 1. Add a custom exception in `src/core/exceptions.py`
echo 2. Create `src/services/my_new_service.py` following the ArcPyService pattern
echo 3. Add a config section in `config/app_config.yaml`
echo 4. Wire the service into `src/runners/main_runner.py`
echo 5. Write tests in `tests/test_services/test_my_new_service.py`
echo.
echo See `docs/HOW_TO_CREATE_NEW_PROJECT.md` for detailed step-by-step instructions.
) > README.md


REM ==============================
REM Done
REM ==============================
echo.
echo ============================================================
echo   Project "%PROJECT_NAME%" created successfully!
echo ============================================================
echo.
echo Files generated:
echo   [x] src/core/             exceptions.py, logger.py, config_loader.py
echo   [x] src/services/         arcpy_service.py, fme_webhook_service.py
echo   [x] src/runners/          main_runner.py
echo   [x] config/               app_config.yaml, logging.yaml, logging.prod.yaml
echo   [x] tests/                conftest.py, test_config_loader.py,
echo                             test_arcpy_service.py, test_fme_webhook_service.py
echo   [x] requirements.txt, requirements.dev.txt, pyproject.toml
echo   [x] .pre-commit-config.yaml, .gitlab-ci.yml, Jenkinsfile, .gitignore
echo   [x] README.md
echo.
echo Next steps:
echo.
echo   1. Open ArcGIS Pro Python Command Prompt
echo   2. conda create --name %PROJECT_NAME%-env --clone arcgispro-py3
echo   3. conda activate %PROJECT_NAME%-env
echo   4. pip install -r requirements.dev.txt
echo   5. pre-commit install
echo   6. Edit config\app_config.yaml with your real paths and URLs
echo   7. python -m src.runners.main_runner --config config/app_config.yaml --logging config/logging.yaml --env DEV
echo.
echo For Jenkins setup, see docs\ in the template repository.
echo.

pause
