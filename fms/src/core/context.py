"""FMS pipeline execution context."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ExecutionContext:
    """
    Runtime context passed to every pipeline step.

    Parameters
    ----------
    env : str
        Target environment — DEV, UAT, or PROD.
    site : str
        Mine site code — WB, ER, TG, JB, or NM.
    source_type : str
        FMS data source — 'minestar' or 'modular'.
    run_timestamp : str
        UTC run timestamp string (YYYYMMDD_HHMM). Auto-generated if empty.
    dry_run : bool
        If True, validate() runs but execute() is skipped on all steps.
    cfg : dict[str, Any]
        Full merged application configuration from YAML.
    site_cfg : dict[str, Any]
        Site-specific configuration slice (from config/sites/<SITE>.yaml).
    """

    env: str
    site: str
    source_type: str
    dry_run: bool
    cfg: dict[str, Any]
    site_cfg: dict[str, Any]
    run_timestamp: str = field(default="")

    # Derived paths — populated by build_paths() after construction
    landing_dir: str = field(default="", init=False)
    staging_dir: str = field(default="", init=False)
    output_dir: str = field(default="", init=False)

    def __post_init__(self) -> None:
        if not self.run_timestamp:
            self.run_timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M")
        self.build_paths()

    def build_paths(self) -> None:
        """Derive landing, staging, and output paths from config."""
        pipeline_cfg: dict[str, Any] = self.cfg.get("pipeline", {})
        paths_cfg: dict[str, Any] = pipeline_cfg.get("paths", {})

        landing_base: str = paths_cfg.get("landing_base", "")
        staging_base: str = paths_cfg.get("staging_base", "")
        output_base: str = paths_cfg.get("output_base", "")

        self.landing_dir = f"{landing_base}/{self.site}" if landing_base else ""
        self.staging_dir = (
            f"{staging_base}/{self.site}/{self.run_timestamp}" if staging_base else ""
        )
        self.output_dir = (
            f"{output_base}/{self.site}/{self.run_timestamp}" if output_base else ""
        )
