"""
ArcPy mosaic dataset service — SDE mosaic operations.

Wraps low-level ArcPy mosaic management calls behind a clean interface
used by MosaicPublisherClientStep in 'direct_sde' mode.

ArcPy is imported lazily so that unit tests run without ArcGIS Pro.
"""
from __future__ import annotations

from typing import Any

from src.core.exceptions import MosaicPublishError
from src.core.logger import get_logger

logger = get_logger(__name__)


class MosaicService:
    """
    Manages operations against an enterprise SDE mosaic dataset.

    Parameters
    ----------
    connection_file : str
        Path to the ArcGIS SDE connection file (.sde) or the .gdb path
        for file geodatabase mosaics.
    """

    def __init__(self, connection_file: str) -> None:
        self.connection_file = connection_file

    def _arcpy(self):
        """Lazy ArcPy import — only available in ArcGIS Pro Python env."""
        try:
            import arcpy  # type: ignore
            return arcpy
        except ImportError as exc:
            raise MosaicPublishError(
                "ArcPy is not available. Run from the ArcGIS Pro conda environment."
            ) from exc

    def add_raster_to_mosaic(
        self,
        mosaic_path: str,
        raster_path: str,
        raster_type: str = "Raster Dataset",
        update_overviews: bool = False,
    ) -> None:
        """
        Add a raster to an existing mosaic dataset.

        Parameters
        ----------
        mosaic_path : str
            Full path to the mosaic dataset (within SDE or file GDB).
        raster_path : str
            Absolute path to the source raster (.tif or similar).
        raster_type : str
            ArcPy raster type string.
        update_overviews : bool
            Whether to rebuild mosaic overviews after adding.

        Raises
        ------
        MosaicPublishError
            If the AddRastersToMosaicDataset call fails.
        """
        arcpy = self._arcpy()
        try:
            logger.info("Adding raster to mosaic: %s → %s", raster_path, mosaic_path)
            arcpy.management.AddRastersToMosaicDataset(
                in_mosaic_dataset=mosaic_path,
                raster_type=raster_type,
                input_path=raster_path,
                update_cellsize_ranges="UPDATE_CELL_SIZES",
                update_boundary="UPDATE_BOUNDARY",
                update_overviews="UPDATE_OVERVIEWS" if update_overviews else "NO_OVERVIEWS",
                duplicate_items_action="OVERWRITE_DUPLICATES",
            )
        except Exception as exc:
            logger.error("AddRastersToMosaicDataset failed: %s", exc, exc_info=True)
            raise MosaicPublishError(
                f"Failed to add raster to mosaic dataset: {mosaic_path}"
            ) from exc

    def synchronise_mosaic(
        self,
        mosaic_path: str,
        update_overviews: bool = False,
    ) -> None:
        """
        Synchronise (update boundaries, cell sizes) a mosaic dataset.

        Parameters
        ----------
        mosaic_path : str
            Full path to the mosaic dataset.
        update_overviews : bool
            Whether to rebuild overviews during sync.

        Raises
        ------
        MosaicPublishError
            If the SynchronizeMosaicDataset call fails.
        """
        arcpy = self._arcpy()
        try:
            logger.info("Synchronising mosaic: %s", mosaic_path)
            arcpy.management.SynchronizeMosaicDataset(
                in_mosaic_dataset=mosaic_path,
                where_clause="",
                new_items=True,
                sync_only_stale=True,
                update_cellsize_ranges=True,
                update_boundary=True,
                update_overviews=update_overviews,
            )
        except Exception as exc:
            logger.error("SynchronizeMosaicDataset failed: %s", exc, exc_info=True)
            raise MosaicPublishError(
                f"Failed to synchronise mosaic dataset: {mosaic_path}"
            ) from exc

    def remove_raster_from_mosaic(
        self, mosaic_path: str, where_clause: str
    ) -> None:
        """
        Remove raster items from a mosaic dataset by attribute query.

        Parameters
        ----------
        mosaic_path : str
            Full path to the mosaic dataset.
        where_clause : str
            SQL WHERE clause identifying items to remove,
            e.g. ``"Name LIKE 'WB_elevation_20251210%'"``

        Raises
        ------
        MosaicPublishError
            If the RemoveRastersFromMosaicDataset call fails.
        """
        arcpy = self._arcpy()
        try:
            logger.info(
                "Removing rasters from %s WHERE %s", mosaic_path, where_clause
            )
            arcpy.management.RemoveRastersFromMosaicDataset(
                in_mosaic_dataset=mosaic_path,
                where_clause=where_clause,
                update_boundary="UPDATE_BOUNDARY",
            )
        except Exception as exc:
            logger.error("RemoveRastersFromMosaicDataset failed: %s", exc, exc_info=True)
            raise MosaicPublishError(
                f"Failed to remove rasters from mosaic: {mosaic_path}"
            ) from exc
