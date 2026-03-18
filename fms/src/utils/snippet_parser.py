"""
Minestar snippet file (.snp) parser.

IMPORTANT — FORMAT NOTE
-----------------------
Minestar snippet files are site-specific proprietary text files.
This parser handles the most common format observed in WAIO environments:

    # Comment / header lines begin with '#'
    <X> <Y> <Z> <ISO8601_DATETIME>   ← whitespace-delimited data rows

Verify the actual delimiter and column order against your specific Minestar
version and site configuration before deploying to production. The
``delimiter`` and column index parameters can be overridden via site config.

Processing pipeline applied to each file:
    1. Parse raw x, y, z, datetime from each data line
    2. Z adjustment  — add configured offset to convert ADPH → AHD datum
    3. Max-Z filter  — discard points where z > max_z
    4. Min-neighbour filter  — remove isolated points with < min_neighbours
       within neighbour_radius metres (grid-based approximation)
    5. Despike       — clamp outlier Z values to a rolling median tolerance
"""
from __future__ import annotations

import math
from typing import Any

from src.core.exceptions import SnippetParseError
from src.core.logger import get_logger

logger = get_logger(__name__)

# Grid cell size (metres) used for the neighbourhood index
_NEIGHBOUR_GRID_M = 5.0


class SnippetParser:
    """
    Parses a single Minestar .snp file and returns filtered point records.

    Parameters
    ----------
    z_adjustment : float
        Constant added to every raw Z value (ADPH→AHD datum conversion).
    max_z : float
        Points with adjusted Z above this value are discarded.
    min_neighbours : int
        Minimum number of other points that must exist within
        ``neighbour_radius`` metres for a point to be retained.
    neighbour_radius : float
        Search radius (metres) for the neighbourhood density filter.
    despike : bool
        Whether to apply the despike (Z-outlier clamping) pass.
    despike_tolerance : float
        Maximum Z deviation (metres) from the local median before a
        point is clamped to ``median ± despike_tolerance``.
    input_sr : str
        Source spatial reference name/WKID string (informational;
        actual reprojection is performed in ElevationProcessingStep).
    output_sr : str
        Target spatial reference name (informational).
    delimiter : str
        Column delimiter.  Defaults to None (splits on any whitespace).
    col_x : int
        Zero-based index of the X column in each data row.
    col_y : int
        Zero-based index of the Y column.
    col_z : int
        Zero-based index of the Z column.
    col_dt : int
        Zero-based index of the datetime column.  -1 means no datetime.
    """

    def __init__(
        self,
        z_adjustment: float = 0.0,
        max_z: float = 4000.0,
        min_neighbours: int = 2,
        neighbour_radius: float = 10.0,
        despike: bool = True,
        despike_tolerance: float = 2.0,
        input_sr: str = "",
        output_sr: str = "MGA50",
        delimiter: str | None = None,
        col_x: int = 0,
        col_y: int = 1,
        col_z: int = 2,
        col_dt: int = 3,
    ) -> None:
        self.z_adjustment = z_adjustment
        self.max_z = max_z
        self.min_neighbours = min_neighbours
        self.neighbour_radius = neighbour_radius
        self.despike = despike
        self.despike_tolerance = despike_tolerance
        self.input_sr = input_sr
        self.output_sr = output_sr
        self.delimiter = delimiter
        self.col_x = col_x
        self.col_y = col_y
        self.col_z = col_z
        self.col_dt = col_dt

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, snp_path: str) -> dict[str, Any]:
        """
        Parse one snippet file and apply all configured filters.

        Parameters
        ----------
        snp_path : str
            Absolute path to the .snp file.

        Returns
        -------
        dict with keys:
            total   — raw point count before any filtering
            valid   — point count after all filters
            points  — list of dicts {x, y, z, datetime}

        Raises
        ------
        SnippetParseError
            If the file cannot be opened or its structure is unrecognised.
        """
        try:
            raw = self._read_raw(snp_path)
        except OSError as exc:
            raise SnippetParseError(f"Cannot read {snp_path}: {exc}") from exc

        total = len(raw)
        if total == 0:
            logger.debug("Empty snippet file: %s", snp_path)
            return {"total": 0, "valid": 0, "points": []}

        # Apply Z adjustment
        pts = self._apply_z_adjustment(raw)

        # Max-Z filter
        pts = [p for p in pts if p["z"] <= self.max_z]

        # Min-neighbour density filter
        if self.min_neighbours > 0:
            pts = self._filter_min_neighbours(pts)

        # Despike
        if self.despike and len(pts) > 3:
            pts = self._despike(pts)

        logger.debug(
            "%s: total=%d  valid=%d (%.1f%%)",
            snp_path,
            total,
            len(pts),
            100.0 * len(pts) / total if total else 0,
        )
        return {"total": total, "valid": len(pts), "points": pts}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_raw(self, path: str) -> list[dict[str, Any]]:
        """Read and parse raw data lines from the snippet file."""
        points: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue  # skip blanks and comment/header lines
                try:
                    parts = (
                        line.split(self.delimiter)
                        if self.delimiter
                        else line.split()
                    )
                    x = float(parts[self.col_x])
                    y = float(parts[self.col_y])
                    z = float(parts[self.col_z])
                    dt = (
                        parts[self.col_dt].strip()
                        if self.col_dt >= 0 and self.col_dt < len(parts)
                        else ""
                    )
                    points.append({"x": x, "y": y, "z": z, "datetime": dt})
                except (IndexError, ValueError) as exc:
                    logger.debug("Skipping malformed line %d in %s: %s", lineno, path, exc)
        return points

    def _apply_z_adjustment(
        self, pts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if self.z_adjustment == 0.0:
            return pts
        return [
            {**p, "z": p["z"] + self.z_adjustment} for p in pts
        ]

    def _filter_min_neighbours(
        self, pts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Grid-based neighbourhood density filter.

        Builds a spatial grid with cell size ``neighbour_radius / 2`` and
        counts points per cell including the 8 surrounding cells.  Points
        with fewer than ``min_neighbours`` total neighbours are discarded.
        """
        cell = max(self.neighbour_radius / 2.0, 1.0)

        grid: dict[tuple[int, int], int] = {}
        for p in pts:
            key = (int(p["x"] // cell), int(p["y"] // cell))
            grid[key] = grid.get(key, 0) + 1

        def _count(p: dict[str, Any]) -> int:
            cx = int(p["x"] // cell)
            cy = int(p["y"] // cell)
            return sum(
                grid.get((cx + dx, cy + dy), 0)
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
            ) - 1  # subtract the point itself

        return [p for p in pts if _count(p) >= self.min_neighbours]

    def _despike(self, pts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Clamp Z outliers to median ± despike_tolerance.

        Uses a global median over all Z values.  For production accuracy,
        a spatially windowed median can be substituted here.
        """
        zvals = sorted(p["z"] for p in pts)
        n = len(zvals)
        median_z = (
            zvals[n // 2]
            if n % 2 == 1
            else (zvals[n // 2 - 1] + zvals[n // 2]) / 2.0
        )
        lo = median_z - self.despike_tolerance
        hi = median_z + self.despike_tolerance

        clamped = 0
        result = []
        for p in pts:
            if lo <= p["z"] <= hi:
                result.append(p)
            else:
                clamped_z = max(lo, min(hi, p["z"]))
                result.append({**p, "z": clamped_z})
                clamped += 1

        if clamped:
            logger.debug("Despike clamped %d points (tol=%.2f)", clamped, self.despike_tolerance)
        return result
