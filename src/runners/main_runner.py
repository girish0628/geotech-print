"""Main runner for GIS automation workflow."""
from __future__ import annotations

import argparse
import sys
from typing import Any

from src.core.config_loader import ConfigLoader, get_config_value
from src.core.logger import setup_logging, get_logger
from src.services.arcpy_service import ArcPyService
from src.services.fme_webhook_service import FMEWebhookService


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="GIS Automation Runner")
    parser.add_argument("--config", required=True, help="Path to app config YAML")
    parser.add_argument("--logging", required=True, help="Path to logging config YAML")
    parser.add_argument("--env", default="DEV", help="Environment ^(DEV/UAT/PROD^)")
    return parser.parse_args()


def run(cfg: dict[str, Any]) -> None:
    """
    Execute workflow steps in order.

    Parameters
    ----------
    cfg : dict[str, Any]
        Loaded application configuration.
    """
    logger = get_logger(__name__)
    logger.info("=" * 60)
    logger.info("GIS Automation Workflow Started")
    logger.info("=" * 60)

    # --- ArcPy Step ---
    workspace = get_config_value(cfg, "arcpy.workspace")
    feature_class = get_config_value(cfg, "arcpy.feature_class")
    fields = get_config_value(cfg, "arcpy.fields", default=[])

    if workspace and feature_class and fields:
        ArcPyService(workspace=workspace).add_fields(
            feature_class=feature_class, fields=fields
        )
        logger.info("ArcPy step complete")
    else:
        logger.warning("Skipping ArcPy step: missing arcpy config keys")

    # --- FME Step ---
    fme_url = get_config_value(cfg, "fme.webhook_url")
    timeout = int(get_config_value(cfg, "fme.timeout", default=60))

    if fme_url:
        resp = FMEWebhookService(webhook_url=fme_url, timeout_s=timeout).trigger(
            payload={"status": "FIELDS_ADDED", "featureClass": feature_class}
        )
        logger.info("FME step complete: response=%s", resp)
    else:
        logger.warning("Skipping FME step: missing fme.webhook_url in config")

    logger.info("=" * 60)
    logger.info("GIS Automation Workflow Completed")
    logger.info("=" * 60)


def main() -> None:
    """Main entry point."""
    try:
        args = parse_args()
        setup_logging(args.logging)
        logger = get_logger(__name__)
        logger.info("Environment: %s", args.env)
        cfg = ConfigLoader(args.config).load()
        run(cfg)
    except Exception:
        get_logger(__name__).error("Workflow failed", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
