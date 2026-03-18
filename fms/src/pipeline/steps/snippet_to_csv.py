"""
Step 1a — Minestar Snippet to CSV.

Reads all .snp files from the site landing zone, applies the full
processing chain (Z adjustment → max-Z filter → noise filter →
despike), and writes a consolidated points.csv + snippet_config.json
to the staging folder.

The CSV is in the input spatial reference at this stage.
Reprojection to MGA50 is delegated to ElevationProcessingStep via ArcPy
(XYTableToPoint with the target coordinate system set on the feature class).
"""
from __future__ import annotations

import csv
import json
import os
from typing import Any

from src.core.context import ExecutionContext
from src.core.exceptions import ValidationError, SnippetParseError
from src.pipeline.base_step import BasePipelineStep
from src.utils.file_utils import ensure_dir, list_files
from src.utils.snippet_parser import SnippetParser


class SnippetToCsvStep(BasePipelineStep):
    """
    Parse Minestar .snp files → consolidated CSV + JSON config.

    Artifacts produced
    ------------------
    csv_path : str
        Absolute path to the output points.csv.
    snippet_config_path : str
        Absolute path to snippet_config.json.
    total_input_points : int
        Raw point count across all snippet files.
    valid_points : int
        Point count after all filters.
    snippet_count : int
        Number of .snp files processed.
    """

    def __init__(self, context: ExecutionContext) -> None:
        super().__init__(context)
        self._snp_files: list[str] = []

    def validate(self) -> None:
        landing = self.context.landing_dir
        if not landing:
            raise ValidationError("landing_dir is not set in ExecutionContext")
        if not os.path.isdir(landing):
            raise ValidationError(f"Landing directory not found: {landing}")

        snp_dir = os.path.join(landing, "snippet")
        self._snp_files = list_files(snp_dir, ".snp")

        if not self._snp_files:
            raise ValidationError(
                f"No .snp files found in: {snp_dir}. "
                "Check GIP delivery or monitoring job."
            )
        self.logger.info(
            "[%s] Found %d snippet files in %s",
            self.name,
            len(self._snp_files),
            snp_dir,
        )

    def execute(self) -> dict[str, Any]:
        site_cfg = self.context.site_cfg
        pipeline_cfg = self.context.cfg.get("pipeline", {})

        parser = SnippetParser(
            z_adjustment=float(site_cfg.get("z_adjustment", 0.0)),
            max_z=float(site_cfg.get("max_z", 4000.0)),
            min_neighbours=int(site_cfg.get("min_neighbours", 2)),
            neighbour_radius=float(site_cfg.get("neighbour_radius", 10.0)),
            despike=bool(site_cfg.get("despike", True)),
            despike_tolerance=float(site_cfg.get("despike_tolerance", 2.0)),
            input_sr=site_cfg.get("input_spatial_reference", ""),
            output_sr=pipeline_cfg.get("output_sr", "MGA50"),
            delimiter=site_cfg.get("snp_delimiter") or None,
            col_x=int(site_cfg.get("snp_col_x", 0)),
            col_y=int(site_cfg.get("snp_col_y", 1)),
            col_z=int(site_cfg.get("snp_col_z", 2)),
            col_dt=int(site_cfg.get("snp_col_dt", 3)),
        )

        ensure_dir(self.context.staging_dir)
        output_csv = os.path.join(self.context.staging_dir, "points.csv")
        config_json_path = os.path.join(self.context.staging_dir, "snippet_config.json")

        total_in = 0
        total_valid = 0
        all_points: list[dict[str, Any]] = []

        for snp_file in self._snp_files:
            self.logger.debug("[%s] Parsing: %s", self.name, snp_file)
            try:
                result = parser.parse(snp_file)
            except SnippetParseError as exc:
                self.logger.warning("[%s] Skipping corrupt file: %s — %s", self.name, snp_file, exc)
                continue

            total_in += result["total"]
            total_valid += result["valid"]
            all_points.extend(result["points"])

        if not all_points:
            raise ValidationError(
                f"All {len(self._snp_files)} snippet files produced zero valid points. "
                "Check z_adjustment, max_z, and min_neighbours configuration."
            )

        # Write consolidated CSV
        with open(output_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["x", "y", "z", "datetime"])
            writer.writeheader()
            writer.writerows(all_points)

        # Write processing config JSON for audit trail
        config_data: dict[str, Any] = {
            "site": self.context.site,
            "run_timestamp": self.context.run_timestamp,
            "source_type": "minestar",
            "snippet_count": len(self._snp_files),
            "total_input_points": total_in,
            "valid_points": total_valid,
            "processing": {
                "z_adjustment": parser.z_adjustment,
                "max_z": parser.max_z,
                "min_neighbours": parser.min_neighbours,
                "despike": parser.despike,
                "input_sr": parser.input_sr,
                "output_sr": parser.output_sr,
            },
        }
        with open(config_json_path, "w", encoding="utf-8") as fh:
            json.dump(config_data, fh, indent=2)

        self.logger.info(
            "[%s] %d files parsed → %d/%d valid points → %s",
            self.name,
            len(self._snp_files),
            total_valid,
            total_in,
            output_csv,
        )

        return {
            "csv_path": output_csv,
            "snippet_config_path": config_json_path,
            "total_input_points": total_in,
            "valid_points": total_valid,
            "snippet_count": len(self._snp_files),
        }
