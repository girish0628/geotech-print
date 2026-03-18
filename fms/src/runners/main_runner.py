"""
FMS Live Surface Pipeline — Jenkins entry point.

Usage (Jenkins 'Run' stage):
    python -m src.runners.main_runner \
        --config  config/app_config.yaml \
        --logging config/logging.prod.yaml \
        --env     PROD \
        --site    WB \
        --source  minestar \
        [--dry-run]

Dry-run mode runs all validate() calls but skips every execute(), making
it safe to verify configuration on a Jenkins node without touching data.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from src.core.config_loader import ConfigLoader, get_config_value
from src.core.context import ExecutionContext
from src.core.exceptions import ConfigLoadError, PipelineStepError
from src.core.logger import setup_logging, get_logger
from src.pipeline.base_step import BasePipelineStep
from src.pipeline.orchestrator import PipelineOrchestrator
from src.pipeline.steps.elevation_processing import ElevationProcessingStep
from src.pipeline.steps.modular_csv_reproject import ModularCsvReprojectStep
from src.pipeline.steps.mosaic_publisher_client import MosaicPublisherClientStep
from src.pipeline.steps.snippet_to_csv import SnippetToCsvStep
from src.pipeline.steps.surface_packager import SurfacePackagerStep

# Valid site codes — extend as new sites are onboarded
VALID_SITES = {"WB", "ER", "TG", "JB", "NM"}
VALID_SOURCES = {"minestar", "modular"}


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments passed by Jenkins."""
    parser = argparse.ArgumentParser(
        description="FMS Live Surface Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", required=True, help="Path to app_config.yaml")
    parser.add_argument("--logging", required=True, help="Path to logging YAML")
    parser.add_argument(
        "--env",
        default="DEV",
        choices=["DEV", "UAT", "PROD"],
        help="Target environment",
    )
    parser.add_argument(
        "--site",
        required=True,
        choices=sorted(VALID_SITES),
        help="Mine site code",
    )
    parser.add_argument(
        "--source",
        default="minestar",
        choices=sorted(VALID_SOURCES),
        help="FMS data source type",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run validate() only — no files written",
    )
    parser.add_argument(
        "--site-config-dir",
        default="config/sites",
        help="Directory containing per-site YAML files",
    )
    return parser.parse_args()


def load_site_config(site: str, site_config_dir: str) -> dict[str, Any]:
    """
    Load the site-specific YAML configuration.

    Parameters
    ----------
    site : str
        Site code, e.g. 'WB'.
    site_config_dir : str
        Directory containing <SITE>.yaml files.

    Returns
    -------
    dict[str, Any]
        Parsed site configuration, or empty dict if file not found.
    """
    import os

    site_yaml = os.path.join(site_config_dir, f"{site}.yaml")
    if not os.path.isfile(site_yaml):
        get_logger(__name__).warning(
            "Site config not found: %s — using defaults from app_config.yaml",
            site_yaml,
        )
        return {}
    return ConfigLoader(site_yaml).load()


def build_steps(
    context: ExecutionContext,
) -> list[BasePipelineStep]:
    """
    Construct the ordered pipeline step list based on source type and mode.

    Pipeline variants:

    DECOUPLED mode (proposed):
        [file-conversion step] → ElevationProcessingStep → SurfacePackagerStep
        (MosaicPublisherClientStep is omitted; publisher polls for ready.flag)

    CURRENT mode (legacy direct publish):
        [file-conversion step] → ElevationProcessingStep
            → SurfacePackagerStep → MosaicPublisherClientStep

    File-conversion step:
        source='minestar' → SnippetToCsvStep
        source='modular'  → ModularCsvReprojectStep

    Parameters
    ----------
    context : ExecutionContext
        Runtime context with cfg, site_cfg, and derived paths.

    Returns
    -------
    list[BasePipelineStep]
        Ordered list of steps to pass to PipelineOrchestrator.
    """
    pipeline_mode: str = get_config_value(context.cfg, "pipeline.mode", "decoupled")

    # Step 1 — file conversion
    if context.source_type == "minestar":
        conversion_step: BasePipelineStep = SnippetToCsvStep(context)
    else:
        conversion_step = ModularCsvReprojectStep(context)

    steps: list[BasePipelineStep] = [
        conversion_step,
        ElevationProcessingStep(context),
        SurfacePackagerStep(context),
    ]

    if pipeline_mode == "current":
        steps.append(MosaicPublisherClientStep(context))

    return steps


def run(
    cfg: dict[str, Any],
    site_cfg: dict[str, Any],
    args: argparse.Namespace,
) -> None:
    """
    Build the execution context and run the pipeline.

    Parameters
    ----------
    cfg : dict[str, Any]
        Full application configuration.
    site_cfg : dict[str, Any]
        Site-specific configuration.
    args : argparse.Namespace
        Parsed CLI arguments.
    """
    logger = get_logger(__name__)

    context = ExecutionContext(
        env=args.env,
        site=args.site,
        source_type=args.source,
        dry_run=args.dry_run,
        cfg=cfg,
        site_cfg=site_cfg,
    )

    logger.info(
        "Context built | landing=%s | staging=%s | output=%s",
        context.landing_dir,
        context.staging_dir,
        context.output_dir,
    )

    steps = build_steps(context)
    orchestrator = PipelineOrchestrator(context, steps)
    orchestrator.run()


def main() -> None:
    """Main entry point — called by Jenkins and __main__."""
    args = parse_args()

    try:
        setup_logging(args.logging)
    except Exception as exc:
        print(f"FATAL: Could not configure logging from {args.logging}: {exc}", file=sys.stderr)
        sys.exit(1)

    logger = get_logger(__name__)
    logger.info(
        "FMS Runner starting | env=%s | site=%s | source=%s | dry_run=%s",
        args.env,
        args.site,
        args.source,
        args.dry_run,
    )

    try:
        cfg = ConfigLoader(args.config).load()
        site_cfg = load_site_config(args.site, args.site_config_dir)
        run(cfg, site_cfg, args)
    except (ConfigLoadError, PipelineStepError) as exc:
        logger.error("Pipeline failed: %s", exc)
        sys.exit(1)
    except Exception:
        logger.error("Unexpected error", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
