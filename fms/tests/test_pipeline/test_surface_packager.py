"""Tests for SurfacePackagerStep."""
from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.core.context import ExecutionContext
from src.core.exceptions import PipelineStepError
from src.pipeline.steps.surface_packager import SurfacePackagerStep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_context(tmp_path, mode: str = "decoupled") -> ExecutionContext:
    output_dir = str(tmp_path / "output" / "WB" / "20251210_0800")
    ctx = ExecutionContext(
        env="DEV",
        site="WB",
        source_type="minestar",
        dry_run=False,
        cfg={
            "pipeline": {
                "mode": mode,
                "paths": {
                    "landing_base": str(tmp_path),
                    "staging_base": str(tmp_path),
                    "output_base": str(tmp_path / "output"),
                    "published_location": str(tmp_path / "published"),
                },
            },
            "mosaic_publisher": {
                "trigger_file_name": "ready.flag",
            },
        },
        site_cfg={},
        run_timestamp="20251210_0800",
    )
    ctx.output_dir = output_dir
    return ctx


def _create_fake_raster(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(b"FAKE_TIFF")


def _create_fake_shp(base_path: str) -> None:
    os.makedirs(os.path.dirname(base_path), exist_ok=True)
    for ext in (".shp", ".dbf", ".shx", ".prj"):
        with open(base_path + ext, "wb") as fh:
            fh.write(b"FAKE")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSurfacePackagerStep:
    def test_validate_fails_when_raster_artifact_missing(self, tmp_path):
        ctx = _make_context(tmp_path)
        step = SurfacePackagerStep(ctx)
        step.artifacts = {}
        with pytest.raises(PipelineStepError, match="Validation failed"):
            step.run()

    def test_validate_fails_when_raster_file_not_found(self, tmp_path):
        ctx = _make_context(tmp_path)
        step = SurfacePackagerStep(ctx)
        step.artifacts = {
            "raster_path": "/nonexistent/raster.tif",
            "boundary_fc_path": "/nonexistent/boundary",
        }
        with pytest.raises(PipelineStepError, match="Validation failed"):
            step.run()

    def test_decoupled_mode_writes_raster_metadata_and_flag(self, tmp_path):
        ctx = _make_context(tmp_path, mode="decoupled")

        raster_src = str(tmp_path / "staging" / "WB_elevation_20251210_0800.tif")
        _create_fake_raster(raster_src)

        shp_base = str(tmp_path / "staging" / "WB_boundary_20251210_0800")
        _create_fake_shp(shp_base)

        step = SurfacePackagerStep(ctx)
        step.artifacts = {
            "raster_path": raster_src,
            "boundary_fc_path": shp_base + ".shp",
            "valid_points": 1000,
            "cell_size": 2.0,
            "output_sr": "GDA 1994 MGA Zone 50",
        }

        # Patch _export_boundary to avoid ArcPy
        with patch.object(step, "_export_boundary", return_value=[shp_base + ".shp"]):
            result = step.run()

        assert "package_dir" in result
        assert os.path.isdir(result["package_dir"])
        assert os.path.isfile(result["output_raster_path"])
        assert os.path.isfile(result["ready_flag_path"])
        assert os.path.isfile(result["metadata_json_path"])

        with open(result["metadata_json_path"]) as fh:
            meta = json.load(fh)
        assert meta["site"] == "WB"
        assert meta["status"] == "ready_for_publish"

    def test_metadata_json_structure(self, tmp_path):
        ctx = _make_context(tmp_path, mode="decoupled")
        raster_src = str(tmp_path / "raster.tif")
        _create_fake_raster(raster_src)

        step = SurfacePackagerStep(ctx)
        step.artifacts = {
            "raster_path": raster_src,
            "boundary_fc_path": raster_src,  # placeholder
            "snippet_count": 1500,
            "total_input_points": 82000,
            "valid_points": 81500,
            "cell_size": 2.0,
            "output_sr": "GDA 1994 MGA Zone 50",
        }

        with patch.object(step, "_export_boundary", return_value=[]):
            result = step.run()

        with open(result["metadata_json_path"]) as fh:
            meta = json.load(fh)

        assert meta["sourceFiles"]["snippetCount"] == 1500
        assert meta["sourceFiles"]["totalPoints"] == 82000
        assert meta["sourceFiles"]["validPoints"] == 81500
        assert meta["processing"]["gridSize"] == 2.0
