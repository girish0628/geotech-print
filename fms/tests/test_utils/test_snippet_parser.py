"""Tests for SnippetParser."""
from __future__ import annotations

import os

import pytest

from src.core.exceptions import SnippetParseError
from src.utils.snippet_parser import SnippetParser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_snp(tmp_path, filename: str, content: str) -> str:
    path = str(tmp_path / filename)
    with open(path, "w") as fh:
        fh.write(content)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSnippetParser:
    def test_parse_valid_file_returns_points(self, tmp_path):
        content = (
            "# header line\n"
            "407100.0 7523400.0 450.0 2025-12-10T07:00:00Z\n"
            "407101.0 7523401.0 451.0 2025-12-10T07:00:05Z\n"
            "407102.0 7523402.0 452.0 2025-12-10T07:00:10Z\n"
        )
        path = _write_snp(tmp_path, "test.snp", content)
        parser = SnippetParser(min_neighbours=0, despike=False)
        result = parser.parse(path)

        assert result["total"] == 3
        assert result["valid"] == 3
        assert len(result["points"]) == 3
        assert result["points"][0]["x"] == pytest.approx(407100.0)
        assert result["points"][0]["z"] == pytest.approx(450.0)

    def test_z_adjustment_applied(self, tmp_path):
        content = "407100.0 7523400.0 400.0 2025-12-10T07:00:00Z\n"
        path = _write_snp(tmp_path, "test.snp", content)
        parser = SnippetParser(z_adjustment=3.155, min_neighbours=0, despike=False)
        result = parser.parse(path)

        assert result["points"][0]["z"] == pytest.approx(403.155)

    def test_max_z_filter(self, tmp_path):
        content = (
            "407100.0 7523400.0 300.0 2025-12-10T07:00:00Z\n"
            "407101.0 7523401.0 5000.0 2025-12-10T07:00:01Z\n"  # above max_z
            "407102.0 7523402.0 301.0 2025-12-10T07:00:02Z\n"
        )
        path = _write_snp(tmp_path, "test.snp", content)
        parser = SnippetParser(max_z=4000.0, min_neighbours=0, despike=False)
        result = parser.parse(path)

        assert result["total"] == 3
        assert result["valid"] == 2

    def test_empty_file_returns_zero_points(self, tmp_path):
        path = _write_snp(tmp_path, "empty.snp", "# just a comment\n")
        parser = SnippetParser()
        result = parser.parse(path)

        assert result["total"] == 0
        assert result["valid"] == 0
        assert result["points"] == []

    def test_malformed_lines_skipped(self, tmp_path):
        content = (
            "not_a_number 7523400.0 450.0 2025-12-10T07:00:00Z\n"
            "407100.0 7523400.0 450.0 2025-12-10T07:00:00Z\n"
        )
        path = _write_snp(tmp_path, "test.snp", content)
        parser = SnippetParser(min_neighbours=0, despike=False)
        result = parser.parse(path)

        assert result["total"] == 1
        assert result["valid"] == 1

    def test_missing_file_raises_snippet_parse_error(self):
        parser = SnippetParser()
        with pytest.raises(SnippetParseError):
            parser.parse("/nonexistent/path/missing.snp")

    def test_despike_clamps_outlier_z(self, tmp_path):
        # Median z ~ 400.0; outlier at 450.0 should be clamped with tolerance=2.0
        content = (
            "407100.0 7523400.0 399.0 2025-12-10T07:00:00Z\n"
            "407101.0 7523401.0 400.0 2025-12-10T07:00:01Z\n"
            "407102.0 7523402.0 401.0 2025-12-10T07:00:02Z\n"
            "407103.0 7523403.0 450.0 2025-12-10T07:00:03Z\n"  # outlier
        )
        path = _write_snp(tmp_path, "test.snp", content)
        parser = SnippetParser(
            min_neighbours=0, despike=True, despike_tolerance=2.0, z_adjustment=0.0
        )
        result = parser.parse(path)

        zvals = [p["z"] for p in result["points"]]
        # Median of [399, 400, 401, 450] = (400 + 401) / 2 = 400.5
        # Clamp ceiling = 400.5 + 2.0 = 402.5; outlier 450 → clamped to 402.5
        assert max(zvals) <= 402.5 + 0.001
        assert 450.0 not in zvals  # original outlier value must be gone

    def test_min_neighbours_filter_removes_isolated_points(self, tmp_path):
        # Two clustered points + one isolated point far away
        content = (
            "407100.0 7523400.0 400.0 2025-12-10T07:00:00Z\n"
            "407100.5 7523400.5 401.0 2025-12-10T07:00:01Z\n"  # close to first
            "500000.0 8000000.0 400.0 2025-12-10T07:00:02Z\n"  # isolated
        )
        path = _write_snp(tmp_path, "test.snp", content)
        parser = SnippetParser(min_neighbours=1, neighbour_radius=5.0, despike=False)
        result = parser.parse(path)

        assert result["valid"] == 2  # isolated point removed
