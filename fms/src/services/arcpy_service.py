"""ArcPy service for GIS geodatabase operations."""
from __future__ import annotations

from typing import Any

from src.core.exceptions import ArcPyExecutionError
from src.core.logger import get_logger

logger = get_logger(__name__)


class ArcPyService:
    """
    Handles ArcPy geodatabase operations.

    Notes
    -----
    ArcPy is imported lazily so unit tests run without ArcGIS Pro installed.
    Always run this service from the ArcGIS Pro cloned conda environment.

    Parameters
    ----------
    workspace : str
        Geodatabase workspace path (file GDB path or SDE connection string).
    """

    def __init__(self, workspace: str) -> None:
        self.workspace = workspace

    def _arcpy(self):
        """Lazy import ArcPy. Only available in ArcGIS Pro Python environment."""
        import arcpy  # type: ignore
        return arcpy

    def add_fields(self, feature_class: str, fields: list[dict[str, Any]]) -> None:
        """
        Add multiple fields to a feature class using config-driven definitions.

        Parameters
        ----------
        feature_class : str
            Feature class name or full path.
        fields : list[dict[str, Any]]
            Field definitions, e.g.:
            [{"name": "MY_FIELD", "type": "TEXT", "length": 100}]

        Raises
        ------
        ArcPyExecutionError
            If any field addition fails.
        """
        try:
            arcpy = self._arcpy()
            arcpy.env.workspace = self.workspace
            for f in fields:
                name = f["name"]
                ftype = f["type"]
                length = f.get("length")
                kwargs: dict[str, Any] = {
                    "in_table": feature_class,
                    "field_name": name,
                    "field_type": ftype,
                }
                if length is not None:
                    kwargs["field_length"] = length
                logger.info("Adding field '%s' ^(%s^) to '%s'", name, ftype, feature_class)
                arcpy.AddField_management(**kwargs)
        except Exception as exc:
            logger.error("add_fields failed for '%s'", feature_class, exc_info=True)
            raise ArcPyExecutionError("Failed to add fields to feature class") from exc

    def calculate_field(
        self, feature_class: str, field_name: str, expression: str
    ) -> None:
        """
        Calculate field values using a Python 3 expression.

        Parameters
        ----------
        feature_class : str
            Feature class name or full path.
        field_name : str
            Name of the field to calculate.
        expression : str
            ArcPy Python 3 field calculator expression.

        Raises
        ------
        ArcPyExecutionError
            If the calculation fails.
        """
        try:
            arcpy = self._arcpy()
            arcpy.env.workspace = self.workspace
            logger.info("Calculating field '%s' on '%s'", field_name, feature_class)
            arcpy.CalculateField_management(
                in_table=feature_class,
                field=field_name,
                expression=expression,
                expression_type="PYTHON3",
            )
        except Exception as exc:
            logger.error("calculate_field failed for '%s'", field_name, exc_info=True)
            raise ArcPyExecutionError("Failed to calculate field") from exc

    def copy_features(self, source: str, destination: str) -> None:
        """
        Copy a feature class to a new location within the workspace.

        Parameters
        ----------
        source : str
            Source feature class name or path.
        destination : str
            Destination feature class name or path.

        Raises
        ------
        ArcPyExecutionError
            If the copy operation fails.
        """
        try:
            arcpy = self._arcpy()
            arcpy.env.workspace = self.workspace
            logger.info("Copying '%s' to '%s'", source, destination)
            arcpy.CopyFeatures_management(
                in_features=source,
                out_feature_class=destination,
            )
        except Exception as exc:
            logger.error("copy_features failed", exc_info=True)
            raise ArcPyExecutionError("Failed to copy features") from exc
