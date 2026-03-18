"""Tests for SnippetToCsvStep."""
from __future__ import annotations

import csv
import os
from typing import Any

import pytest

from src.core.context import ExecutionContext
from src.core.exceptions import PipelineStepError, ValidationError
from src.pipeline.steps.snippet_to_csv import SnippetToCsvStep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_context(
    tmp_path,
    landing_override: str = "",
    staging_override: str = "",
    site_cfg: dict[str, Any] | None = None,
) -> ExecutionContext:
    landing = landing_override or str(tmp_path / "landing")
    staging = staging_override or str(tmp_path / "staging")

    ctx = ExecutionContext(
        env="DEV",
        site="WB",
        source_type="minestar",
        dry_run=False,
        cfg={
            "pipeline": {
                "output_sr": "GDA 1994 MGA Zone 50",
                "paths": {
                    "landing_base": str(tmp_path / "landing_base"),
                    "staging_base": str(tmp_path / "staging_base"),
                    "output_base": str(tmp_path / "output_base"),
                },
            }
        },
        site_cfg=site_cfg or {
            "z_adjustment": 1.0,
            "max_z": 4000.0,
            "min_neighbours": 0,  # disable neighbour filter in tests
            "despike": False,
        },
        run_timestamp="20251210_0800",
    )
    # Override derived paths to point at tmp_path locations
    ctx.landing_dir = landing
    ctx.staging_dir = staging
    return ctx


def _make_snp_file(directory: str, filename: str = "test.snp", n_points: int = 5) -> str:
    """Write a simple whitespace-delimited snippet file."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    with open(path, "w") as fh:
        fh.write("# FMS Snippet File\n")
        for i in range(n_points):
            fh.write(f"407100.{i:03d} 7523400.{i:03d} 450.{i:03d} 2025-12-10T07:00:{i:02d}Z\n")
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSnippetToCsvStep:
    def test_validate_fails_when_landing_dir_missing(self, tmp_path):
        ctx = _make_context(tmp_path, landing_override="/nonexistent/path")
        step = SnippetToCsvStep(ctx)
        with pytest.raises(PipelineStepError, match="Validation failed"):
            step.run()

    def test_validate_fails_when_no_snp_files(self, tmp_path):
        landing = str(tmp_path / "landing")
        os.makedirs(os.path.join(landing, "snippet"), exist_ok=True)
        ctx = _make_context(tmp_path, landing_override=landing)
        step = SnippetToCsvStep(ctx)
        with pytest.raises(PipelineStepError, match="Validation failed"):
            step.run()

    def test_execute_produces_csv_and_config_json(self, tmp_path):
        landing = str(tmp_path / "landing")
        staging = str(tmp_path / "staging")
        snp_dir = os.path.join(landing, "snippet")
        _make_snp_file(snp_dir, n_points=10)

        ctx = _make_context(tmp_path, landing_override=landing, staging_override=staging)
        step = SnippetToCsvStep(ctx)
        result = step.run()

        assert "csv_path" in result
        assert os.path.isfile(result["csv_path"])

        assert "snippet_config_path" in result
        assert os.path.isfile(result["snippet_config_path"])

    def test_csv_contains_expected_columns(self, tmp_path):
        landing = str(tmp_path / "landing")
        staging = str(tmp_path / "staging")
        snp_dir = os.path.join(landing, "snippet")
        _make_snp_file(snp_dir, n_points=3)

        ctx = _make_context(tmp_path, landing_override=landing, staging_override=staging)
        step = SnippetToCsvStep(ctx)
        result = step.run()

        with open(result["csv_path"]) as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)

        assert len(rows) == 3
        assert set(rows[0].keys()) == {"x", "y", "z", "datetime"}

    def test_z_adjustment_applied(self, tmp_path):
        landing = str(tmp_path / "landing")
        staging = str(tmp_path / "staging")
        snp_dir = os.path.join(landing, "snippet")
        _make_snp_file(snp_dir, n_points=1)

        ctx = _make_context(
            tmp_path,
            landing_override=landing,
            staging_override=staging,
            site_cfg={
                "z_adjustment": 100.0,
                "max_z": 10000.0,
                "min_neighbours": 0,
                "despike": False,
            },
        )
        step = SnippetToCsvStep(ctx)
        result = step.run()

        with open(result["csv_path"]) as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)

        # Raw z is 450.000; with +100.0 adjustment should be ~550.0
        assert float(rows[0]["z"]) > 500.0

    def test_max_z_filter_removes_high_points(self, tmp_path):
        landing = str(tmp_path / "landing")
        staging = str(tmp_path / "staging")
        snp_dir = os.path.join(landing, "snippet")

        # Write file with one high-z point
        os.makedirs(snp_dir, exist_ok=True)
        snp_path = os.path.join(snp_dir, "test.snp")
        with open(snp_path, "w") as fh:
            fh.write("407100.0 7523400.0 200.0 2025-12-10T07:00:00Z\n")
            fh.write("407101.0 7523401.0 9999.0 2025-12-10T07:00:01Z\n")  # above max_z
            fh.write("407102.0 7523402.0 201.0 2025-12-10T07:00:02Z\n")

        ctx = _make_context(
            tmp_path,
            landing_override=landing,
            staging_override=staging,
            site_cfg={"z_adjustment": 0.0, "max_z": 500.0, "min_neighbours": 0, "despike": False},
        )
        step = SnippetToCsvStep(ctx)
        result = step.run()

        assert result["valid_points"] == 2
        assert result["total_input_points"] == 3

    def test_dry_run_skips_execute(self, tmp_path):
        landing = str(tmp_path / "landing")
        staging = str(tmp_path / "staging")
        snp_dir = os.path.join(landing, "snippet")
        _make_snp_file(snp_dir, n_points=3)

        ctx = _make_context(tmp_path, landing_override=landing, staging_override=staging)
        ctx.dry_run = True
        step = SnippetToCsvStep(ctx)
        result = step.run()

        assert result == {}
        assert not os.path.isdir(staging)
