"""
Step 2 — Elevation Processing.

Converts the consolidated points CSV (from Step 1a or 1b) into:
    1. 3D point feature class (XYTableToPoint)
    2. TIN (CreateTin — Delaunay triangulation)
    3. Elevation raster in GeoTIFF format (TinRaster)
    4. Boundary polygon — convex hull of the point cloud (MinimumBoundingGeometry)
    5. Roads exclusion applied if MTD_Live_RoadsBuffered is configured (Erase)
    6. Raster clipped to final boundary polygon (Clip)

All intermediate data is written to a scratch file geodatabase inside
the staging directory and cleaned up unless ``keep_scratch`` is True.

Reads artifacts from previous step:
    csv_path — path to the MGA50-referenced points CSV

Artifacts produced:
    raster_path        — clipped GeoTIFF elevation raster
    boundary_fc_path   — boundary polygon (file GDB feature class)
    tin_path           — TIN dataset path
    cell_size          — raster cell size used
    output_sr          — output spatial reference string
    feature_class_path — 3D point feature class path
"""
from __future__ import annotations

import os
from typing import Any

from src.core.context import ExecutionContext
from src.core.exceptions import ValidationError, ElevationProcessingError
from src.pipeline.base_step import BasePipelineStep
from src.utils.file_utils import ensure_dir


class ElevationProcessingStep(BasePipelineStep):
    """
    CSV → 3D Feature Class → TIN → Raster + Boundary.

    Requires ArcGIS 3D Analyst and Spatial Analyst extensions.
    Run from the ArcGIS Pro cloned conda environment.
    """

    def validate(self) -> None:
        csv_path: str = self.artifacts.get("csv_path", "")
        if not csv_path:
            raise ValidationError(
                "csv_path artifact not found. "
                "SnippetToCsvStep or ModularCsvReprojectStep must run first."
            )
        if not os.path.isfile(csv_path):
            raise ValidationError(f"Input CSV does not exist: {csv_path}")

        staging = self.context.staging_dir
        if not staging:
            raise ValidationError("staging_dir is not set in ExecutionContext")

        self.logger.info("[%s] Input CSV: %s", self.name, csv_path)

    def execute(self) -> dict[str, Any]:  # noqa: PLR0915 (complex but sequential)
        try:
            import arcpy  # type: ignore
            import arcpy.ddd  # type: ignore
            import arcpy.management  # type: ignore
            import arcpy.analysis  # type: ignore
        except ImportError as exc:
            raise ElevationProcessingError(
                "ArcPy not available. Run from ArcGIS Pro conda environment."
            ) from exc

        csv_path: str = self.artifacts["csv_path"]
        site_cfg = self.context.site_cfg
        pipeline_cfg = self.context.cfg.get("pipeline", {})

        cell_size: float = float(
            site_cfg.get("grid_size", pipeline_cfg.get("default_grid_size", 2.0))
        )
        output_sr_name: str = pipeline_cfg.get("output_sr", "MGA50")
        roads_buffer_fc: str = pipeline_cfg.get("roads_buffer_fc", "")
        keep_scratch: bool = bool(pipeline_cfg.get("keep_scratch", False))

        site: str = self.context.site
        ts: str = self.context.run_timestamp
        staging: str = self.context.staging_dir

        ensure_dir(staging)

        # ----------------------------------------------------------------
        # Scratch geodatabase
        # ----------------------------------------------------------------
        scratch_gdb = os.path.join(staging, "scratch.gdb")
        arcpy.env.overwriteOutput = True
        if not arcpy.Exists(scratch_gdb):
            arcpy.management.CreateFileGDB(staging, "scratch.gdb")
        arcpy.env.workspace = scratch_gdb

        sr = arcpy.SpatialReference(output_sr_name)

        # ----------------------------------------------------------------
        # A: CSV → 3D point feature class
        # ----------------------------------------------------------------
        fc_name = f"{site}_points_{ts}"
        fc_path = os.path.join(scratch_gdb, fc_name)
        self.logger.info("[%s] A — CSV → 3D Feature Class: %s", self.name, fc_path)

        arcpy.management.XYTableToPoint(
            in_table=csv_path,
            out_feature_class=fc_path,
            x_field="x",
            y_field="y",
            z_field="z",
            coordinate_system=sr,
        )
        pt_count = int(arcpy.management.GetCount(fc_path).getOutput(0))
        self.logger.info("[%s] Feature class created: %d points", self.name, pt_count)

        # ----------------------------------------------------------------
        # B: 3D Feature Class → TIN
        # ----------------------------------------------------------------
        tin_path = os.path.join(staging, f"{site}_tin_{ts}")
        self.logger.info("[%s] B — 3D FC → TIN: %s", self.name, tin_path)

        arcpy.ddd.CreateTin(
            out_tin=tin_path,
            spatial_reference=sr,
            in_features=f"{fc_path} z masspoints",
        )

        # ----------------------------------------------------------------
        # C: TIN → Raster (GeoTIFF, Float32)
        # ----------------------------------------------------------------
        raster_name = f"{site}_elevation_{ts}.tif"
        raster_path = os.path.join(staging, raster_name)
        self.logger.info(
            "[%s] C — TIN → Raster (cellsize=%.1fm): %s",
            self.name,
            cell_size,
            raster_path,
        )

        arcpy.ddd.TinRaster(
            in_tin=tin_path,
            out_raster=raster_path,
            data_type="FLOAT",
            method="LINEAR",
            sample_distance=f"CELLSIZE {cell_size}",
        )

        # ----------------------------------------------------------------
        # D: Boundary — convex hull of point cloud
        # ----------------------------------------------------------------
        boundary_name = f"{site}_boundary_{ts}"
        boundary_raw = os.path.join(scratch_gdb, boundary_name + "_raw")
        self.logger.info("[%s] D — Generating boundary polygon: %s", self.name, boundary_raw)

        arcpy.management.MinimumBoundingGeometry(
            in_features=fc_path,
            out_feature_class=boundary_raw,
            geometry_type="CONVEX_HULL",
            group_option="ALL",
        )

        # ----------------------------------------------------------------
        # E: Erase roads exclusion zone (optional)
        # ----------------------------------------------------------------
        boundary_fc_path = boundary_raw
        if roads_buffer_fc and arcpy.Exists(roads_buffer_fc):
            boundary_erased = os.path.join(scratch_gdb, boundary_name + "_erased")
            self.logger.info(
                "[%s] E — Applying roads exclusion: %s", self.name, roads_buffer_fc
            )
            arcpy.analysis.Erase(
                in_features=boundary_raw,
                erase_features=roads_buffer_fc,
                out_feature_class=boundary_erased,
            )
            boundary_fc_path = boundary_erased
        else:
            if roads_buffer_fc:
                self.logger.warning(
                    "[%s] roads_buffer_fc configured but not found: %s — skipping exclusion",
                    self.name,
                    roads_buffer_fc,
                )

        # ----------------------------------------------------------------
        # F: Clip raster to final boundary
        # ----------------------------------------------------------------
        clipped_raster = os.path.join(staging, f"{site}_elevation_clipped_{ts}.tif")
        self.logger.info("[%s] F — Clipping raster to boundary: %s", self.name, clipped_raster)

        arcpy.management.Clip(
            in_raster=raster_path,
            rectangle="#",
            out_raster=clipped_raster,
            in_template_dataset=boundary_fc_path,
            clipping_geometry="ClippingGeometry",
            maintain_clipping_extent="NO_MAINTAIN_EXTENT",
        )

        if not keep_scratch:
            self.logger.debug("[%s] Removing scratch GDB: %s", self.name, scratch_gdb)
            try:
                arcpy.management.Delete(scratch_gdb)
            except Exception as exc:
                self.logger.warning(
                    "[%s] Could not remove scratch GDB: %s", self.name, exc
                )

        self.logger.info(
            "[%s] Elevation processing complete — raster: %s", self.name, clipped_raster
        )

        return {
            "raster_path": clipped_raster,
            "tin_path": tin_path,
            "boundary_fc_path": boundary_fc_path,
            "feature_class_path": fc_path,
            "cell_size": cell_size,
            "output_sr": output_sr_name,
        }
