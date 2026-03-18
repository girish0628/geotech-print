"""
Step 3 — Surface Packager.

Assembles the final "Surface Package" in the output directory:

    <output_base>/<site>/<timestamp>/
        <site>_elevation_<ts>.tif      — clipped elevation raster
        <site>_boundary_<ts>.shp/...   — boundary polygon sidecar files
        metadata.json                  — processing metadata (audit trail)
        ready.flag                     — trigger file for the mosaic publisher

The ready.flag is written last so that the publishing solution only
picks up a complete package.

If ``pipeline.mode`` is 'current' (legacy direct-publish), the packager
instead copies artefacts to the ``published_location`` path used by
MosaicPublisherClientStep and does NOT write a ready.flag.

Reads artifacts from previous steps:
    raster_path        — clipped GeoTIFF from ElevationProcessingStep
    boundary_fc_path   — boundary feature class from ElevationProcessingStep
    cell_size          — raster cell size
    output_sr          — output spatial reference string
    valid_points       — point count from file-conversion step
    snippet_count      — (optional) number of .snp files processed
    csv_count          — (optional) number of modular CSV files processed

Artifacts produced:
    package_dir        — absolute path to the assembled package directory
    output_raster_path — final raster path inside the package
    metadata_json_path — metadata.json path
    ready_flag_path    — ready.flag path (decoupled mode only)
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from typing import Any

from src.core.context import ExecutionContext
from src.core.exceptions import ValidationError, SurfacePackageError
from src.pipeline.base_step import BasePipelineStep
from src.utils.file_utils import (
    copy_file,
    copy_shapefile,
    ensure_dir,
    write_flag_file,
)


class SurfacePackagerStep(BasePipelineStep):
    """
    Assemble the output Surface Package directory.

    Supports two packaging modes controlled by ``pipeline.mode``:
        'decoupled' (default/proposed) — write to output_dir + ready.flag
        'current'                      — copy to published_location (legacy)
    """

    def validate(self) -> None:
        raster_path: str = self.artifacts.get("raster_path", "")
        if not raster_path:
            raise ValidationError(
                "raster_path artifact missing. ElevationProcessingStep must run first."
            )
        if not os.path.isfile(raster_path):
            raise ValidationError(f"Raster file not found: {raster_path}")

        boundary_path: str = self.artifacts.get("boundary_fc_path", "")
        if not boundary_path:
            raise ValidationError("boundary_fc_path artifact missing.")

        mode = self._packaging_mode()
        if mode == "current":
            published = self._published_location()
            if not published:
                raise ValidationError(
                    "pipeline.published_location must be set when pipeline.mode='current'."
                )
        else:
            if not self.context.output_dir:
                raise ValidationError("output_dir is not set in ExecutionContext.")

        self.logger.info("[%s] Packaging mode: %s", self.name, mode)

    def execute(self) -> dict[str, Any]:
        mode = self._packaging_mode()
        if mode == "current":
            return self._package_current_mode()
        return self._package_decoupled_mode()

    # ------------------------------------------------------------------
    # Mode implementations
    # ------------------------------------------------------------------

    def _package_decoupled_mode(self) -> dict[str, Any]:
        """Write package to output_dir + ready.flag (proposed workflow)."""
        package_dir = self.context.output_dir
        ensure_dir(package_dir)

        raster_src: str = self.artifacts["raster_path"]
        boundary_src: str = self.artifacts["boundary_fc_path"]
        site = self.context.site
        ts = self.context.run_timestamp

        # Copy raster
        raster_dst_name = f"{site}_elevation_{ts}.tif"
        raster_dst = os.path.join(package_dir, raster_dst_name)
        self.logger.info("[%s] Copying raster → %s", self.name, raster_dst)
        shutil.copy2(raster_src, raster_dst)

        # Copy boundary (shapefile sidecar files or GDB feature class export)
        boundary_files = self._export_boundary(boundary_src, package_dir, site, ts)

        # Write metadata.json
        metadata = self._build_metadata(raster_dst_name, boundary_files)
        meta_path = os.path.join(package_dir, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2)
        self.logger.info("[%s] metadata.json written: %s", self.name, meta_path)

        # Write ready.flag LAST — signals a complete package
        flag_name: str = (
            self.context.cfg.get("mosaic_publisher", {}).get(
                "trigger_file_name", "ready.flag"
            )
        )
        flag_path = write_flag_file(package_dir, flag_name)
        self.logger.info("[%s] Surface package ready: %s", self.name, package_dir)

        return {
            "package_dir": package_dir,
            "output_raster_path": raster_dst,
            "metadata_json_path": meta_path,
            "ready_flag_path": flag_path,
        }

    def _package_current_mode(self) -> dict[str, Any]:
        """Copy artefacts to published_location (legacy direct-publish workflow)."""
        published_location: str = self._published_location()
        ensure_dir(published_location)

        raster_src: str = self.artifacts["raster_path"]
        boundary_src: str = self.artifacts["boundary_fc_path"]
        site = self.context.site
        ts = self.context.run_timestamp

        raster_dst = copy_file(raster_src, published_location)
        self.logger.info("[%s] (current mode) Raster copied → %s", self.name, raster_dst)

        boundary_files = self._export_boundary(boundary_src, published_location, site, ts)

        # Also copy source CSV for internal access
        csv_src: str = self.artifacts.get("csv_path", "")
        if csv_src and os.path.isfile(csv_src):
            copy_file(csv_src, published_location)

        metadata = self._build_metadata(os.path.basename(raster_dst), boundary_files)
        meta_path = os.path.join(published_location, "metadata.json")
        with open(meta_path, "w", encoding="utf-8") as fh:
            json.dump(metadata, fh, indent=2)

        self.logger.info(
            "[%s] (current mode) Package at published location: %s",
            self.name,
            published_location,
        )

        return {
            "package_dir": published_location,
            "output_raster_path": raster_dst,
            "metadata_json_path": meta_path,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _export_boundary(
        self, boundary_src: str, dst_dir: str, site: str, ts: str
    ) -> list[str]:
        """
        Export boundary to shapefile in dst_dir.

        Handles both:
        - File GDB feature class  → export via ArcPy CopyFeatures
        - Existing shapefile      → copy sidecar files directly
        """
        shp_base = os.path.join(dst_dir, f"{site}_boundary_{ts}")

        if boundary_src.endswith(".shp") and os.path.isfile(boundary_src):
            return copy_shapefile(boundary_src, dst_dir)

        # Assume file GDB feature class — export to shapefile
        try:
            import arcpy  # type: ignore

            out_shp = shp_base + ".shp"
            arcpy.management.CopyFeatures(
                in_features=boundary_src,
                out_feature_class=out_shp,
            )
            return [
                f for f in [
                    out_shp,
                    shp_base + ".dbf",
                    shp_base + ".shx",
                    shp_base + ".prj",
                ]
                if os.path.isfile(f)
            ]
        except Exception as exc:
            raise SurfacePackageError(
                f"Failed to export boundary to shapefile: {exc}"
            ) from exc

    def _build_metadata(
        self, raster_filename: str, boundary_files: list[str]
    ) -> dict[str, Any]:
        """Construct the metadata.json payload."""
        boundary_shp = next(
            (os.path.basename(f) for f in boundary_files if f.endswith(".shp")), ""
        )
        return {
            "site": self.context.site,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "run_timestamp": self.context.run_timestamp,
            "env": self.context.env,
            "source_type": self.context.source_type,
            "sourceFiles": {
                "snippetCount": self.artifacts.get("snippet_count", 0),
                "csvCount": self.artifacts.get("csv_count", 0),
                "totalPoints": self.artifacts.get("total_input_points", 0),
                "validPoints": self.artifacts.get("valid_points", 0),
            },
            "processing": {
                "gridSize": self.artifacts.get("cell_size", 2.0),
                "spatialReference": self.artifacts.get("output_sr", "MGA50"),
            },
            "output": {
                "rasterPath": raster_filename,
                "boundaryPath": boundary_shp,
                "cellSize": self.artifacts.get("cell_size", 2.0),
                "format": "GeoTIFF",
            },
            "status": "ready_for_publish",
        }

    def _packaging_mode(self) -> str:
        return self.context.cfg.get("pipeline", {}).get("mode", "decoupled")

    def _published_location(self) -> str:
        return (
            self.context.cfg.get("pipeline", {})
            .get("paths", {})
            .get("published_location", "")
        )
