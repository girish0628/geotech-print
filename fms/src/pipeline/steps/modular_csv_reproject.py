"""
Step 1b — Modular CSV Reprojection.

Reads CSV files from the site landing zone (WB94 or ER94 coordinate
system), reprojects each point to MGA50 via ArcPy, and writes a
consolidated points.csv to the staging folder.

Used as an alternative to SnippetToCsvStep when the source system is
Modular (not Minestar).  Both steps emit the same ``csv_path`` artifact,
so ElevationProcessingStep is agnostic to the upstream source.
"""
from __future__ import annotations

import csv
import json
import os
from typing import Any

from src.core.context import ExecutionContext
from src.core.exceptions import ValidationError, ElevationProcessingError
from src.pipeline.base_step import BasePipelineStep
from src.utils.file_utils import ensure_dir, list_files


class ModularCsvReprojectStep(BasePipelineStep):
    """
    Reproject Modular CSV files from WB94/ER94 → MGA50.

    Artifacts produced
    ------------------
    csv_path : str
        Absolute path to the reprojected points.csv.
    valid_points : int
        Total rows successfully reprojected.
    csv_count : int
        Number of source CSV files processed.
    """

    def __init__(self, context: ExecutionContext) -> None:
        super().__init__(context)
        self._csv_files: list[str] = []

    def validate(self) -> None:
        landing = self.context.landing_dir
        if not landing:
            raise ValidationError("landing_dir is not set in ExecutionContext")
        if not os.path.isdir(landing):
            raise ValidationError(f"Landing directory not found: {landing}")

        csv_dir = os.path.join(landing, "csv")
        self._csv_files = list_files(csv_dir, ".csv")

        if not self._csv_files:
            raise ValidationError(
                f"No CSV files found in: {csv_dir}. "
                "Check GIP delivery or monitoring job."
            )
        self.logger.info(
            "[%s] Found %d modular CSV files in %s",
            self.name,
            len(self._csv_files),
            csv_dir,
        )

    def execute(self) -> dict[str, Any]:
        site_cfg = self.context.site_cfg
        pipeline_cfg = self.context.cfg.get("pipeline", {})

        input_sr_name: str = site_cfg.get("input_spatial_reference", "WGS 1984")
        output_sr_name: str = pipeline_cfg.get("output_sr", "MGA50")
        x_col: str = site_cfg.get("modular_x_col", "Easting")
        y_col: str = site_cfg.get("modular_y_col", "Northing")
        z_col: str = site_cfg.get("modular_z_col", "Elevation")
        dt_col: str = site_cfg.get("modular_datetime_col", "Timestamp")
        max_z: float = float(site_cfg.get("max_z", 4000.0))
        z_adjustment: float = float(site_cfg.get("z_adjustment", 0.0))

        try:
            import arcpy  # type: ignore
        except ImportError as exc:
            raise ElevationProcessingError(
                "ArcPy is not available. Run from ArcGIS Pro conda environment."
            ) from exc

        in_sr = arcpy.SpatialReference(input_sr_name)
        out_sr = arcpy.SpatialReference(output_sr_name)

        ensure_dir(self.context.staging_dir)
        output_csv = os.path.join(self.context.staging_dir, "points.csv")

        all_rows: list[dict[str, Any]] = []
        skipped = 0

        for csv_path in self._csv_files:
            self.logger.debug("[%s] Processing: %s", self.name, csv_path)
            with open(csv_path, "r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    try:
                        x = float(row[x_col])
                        y = float(row[y_col])
                        z = float(row[z_col]) + z_adjustment
                        dt = row.get(dt_col, "")

                        if z > max_z:
                            skipped += 1
                            continue

                        pt = arcpy.PointGeometry(arcpy.Point(x, y), in_sr)
                        proj = pt.projectAs(out_sr)
                        all_rows.append(
                            {
                                "x": proj.centroid.X,
                                "y": proj.centroid.Y,
                                "z": z,
                                "datetime": dt,
                            }
                        )
                    except (KeyError, ValueError) as exc:
                        self.logger.warning(
                            "[%s] Malformed row skipped in %s: %s",
                            self.name,
                            csv_path,
                            exc,
                        )
                        skipped += 1

        if not all_rows:
            raise ValidationError(
                "Modular CSV reprojection produced zero valid points. "
                "Check column names and spatial reference configuration."
            )

        with open(output_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["x", "y", "z", "datetime"])
            writer.writeheader()
            writer.writerows(all_rows)

        self.logger.info(
            "[%s] %d files → %d valid points (%d skipped) → %s",
            self.name,
            len(self._csv_files),
            len(all_rows),
            skipped,
            output_csv,
        )

        return {
            "csv_path": output_csv,
            "valid_points": len(all_rows),
            "csv_count": len(self._csv_files),
        }
