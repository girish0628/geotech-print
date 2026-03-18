"""
Step 4 — Mosaic Publisher Client.

Integrates with the Enterprise Mosaic Publisher service to register the
completed Surface Package into the SDE mosaic dataset.

Supports three integration modes (configured via ``mosaic_publisher.integration_mode``):

    'file_trigger'   (default/proposed)
        The Surface Package already contains a ready.flag written by
        SurfacePackagerStep.  This step simply logs the handoff path
        and optionally performs a lightweight API ping to notify the
        publisher that a new package is waiting.

    'api_call'
        Makes an HTTP POST to the publisher API endpoint with the
        package directory path and metadata.  Used when the publisher
        exposes a REST interface.

    'direct_sde'
        Directly calls ArcPy AddRastersToMosaicDataset on the enterprise
        SDE mosaic dataset.  This is the 'current' (legacy) mode.

Reads artifacts from previous steps:
    package_dir        — path to the assembled Surface Package
    output_raster_path — final raster path
    metadata_json_path — metadata.json path

Artifacts produced:
    publish_status     — 'submitted' | 'triggered' | 'direct_published'
    publish_detail     — human-readable result detail
"""
from __future__ import annotations

import json
import os
from typing import Any

import requests

from src.core.context import ExecutionContext
from src.core.exceptions import ValidationError, MosaicPublishError
from src.pipeline.base_step import BasePipelineStep


class MosaicPublisherClientStep(BasePipelineStep):
    """
    Handoff to the Enterprise Mosaic Publisher service.

    Included in the pipeline when ``pipeline.mode`` is 'current' (direct_sde)
    or when the publisher needs an explicit API notification after the
    Surface Package is written.

    In 'decoupled' mode with 'file_trigger', this step is optional —
    the publisher polls for ready.flag independently.
    """

    def validate(self) -> None:
        package_dir: str = self.artifacts.get("package_dir", "")
        if not package_dir:
            raise ValidationError(
                "package_dir artifact missing. SurfacePackagerStep must run first."
            )
        if not os.path.isdir(package_dir):
            raise ValidationError(f"Package directory not found: {package_dir}")

        mode = self._integration_mode()
        self.logger.info("[%s] Integration mode: %s", self.name, mode)

        if mode == "api_call":
            endpoint = self._api_endpoint()
            if not endpoint:
                raise ValidationError(
                    "mosaic_publisher.api_endpoint must be set for integration_mode='api_call'."
                )

        if mode == "direct_sde":
            sde_cfg = self.context.cfg.get("sde", {})
            if not sde_cfg.get("connection_file"):
                raise ValidationError(
                    "sde.connection_file must be set for integration_mode='direct_sde'."
                )
            if not sde_cfg.get("source_mosaic"):
                raise ValidationError(
                    "sde.source_mosaic must be set for integration_mode='direct_sde'."
                )

    def execute(self) -> dict[str, Any]:
        mode = self._integration_mode()

        if mode == "file_trigger":
            return self._trigger_via_flag()
        if mode == "api_call":
            return self._trigger_via_api()
        if mode == "direct_sde":
            return self._publish_direct_sde()

        raise MosaicPublishError(
            f"Unknown integration_mode: {mode!r}. "
            "Valid options: file_trigger | api_call | direct_sde"
        )

    # ------------------------------------------------------------------
    # Integration mode implementations
    # ------------------------------------------------------------------

    def _trigger_via_flag(self) -> dict[str, Any]:
        """
        File-trigger mode — the ready.flag was written by SurfacePackagerStep.

        Optionally ping a notification endpoint to wake the publisher.
        """
        package_dir: str = self.artifacts["package_dir"]
        flag_path: str = self.artifacts.get("ready_flag_path", "")

        if not flag_path:
            flag_path = os.path.join(
                package_dir,
                self.context.cfg.get("mosaic_publisher", {}).get(
                    "trigger_file_name", "ready.flag"
                ),
            )

        if not os.path.isfile(flag_path):
            raise MosaicPublishError(
                f"Expected ready.flag not found: {flag_path}. "
                "Ensure SurfacePackagerStep completed successfully."
            )

        self.logger.info(
            "[%s] Surface package ready for publisher polling: %s",
            self.name,
            package_dir,
        )

        # Optional lightweight API ping — fire and forget
        notify_url: str = (
            self.context.cfg.get("mosaic_publisher", {}).get("notify_url", "")
        )
        if notify_url:
            try:
                timeout: int = int(
                    self.context.cfg.get("mosaic_publisher", {}).get("timeout", 30)
                )
                resp = requests.post(
                    notify_url,
                    json={"package_dir": package_dir, "site": self.context.site},
                    timeout=timeout,
                )
                resp.raise_for_status()
                self.logger.info(
                    "[%s] Publisher notified at %s — HTTP %d",
                    self.name,
                    notify_url,
                    resp.status_code,
                )
            except requests.RequestException as exc:
                # Non-fatal — publisher will pick up flag on next poll cycle
                self.logger.warning(
                    "[%s] Publisher notification failed (non-fatal): %s", self.name, exc
                )

        return {
            "publish_status": "triggered",
            "publish_detail": f"ready.flag at {flag_path}",
        }

    def _trigger_via_api(self) -> dict[str, Any]:
        """POST the package metadata to the publisher REST API."""
        endpoint: str = self._api_endpoint()
        pub_cfg = self.context.cfg.get("mosaic_publisher", {})
        timeout: int = int(pub_cfg.get("timeout", 60))

        package_dir: str = self.artifacts["package_dir"]
        meta_path: str = self.artifacts.get("metadata_json_path", "")
        metadata: dict[str, Any] = {}
        if meta_path and os.path.isfile(meta_path):
            with open(meta_path, "r", encoding="utf-8") as fh:
                metadata = json.load(fh)

        payload: dict[str, Any] = {
            "package_dir": package_dir,
            "site": self.context.site,
            "run_timestamp": self.context.run_timestamp,
            "metadata": metadata,
        }

        self.logger.info("[%s] POST to publisher API: %s", self.name, endpoint)
        try:
            resp = requests.post(endpoint, json=payload, timeout=timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise MosaicPublishError(
                f"Publisher API call failed: {exc}"
            ) from exc

        self.logger.info(
            "[%s] Publisher API accepted package — HTTP %d", self.name, resp.status_code
        )
        return {
            "publish_status": "submitted",
            "publish_detail": f"HTTP {resp.status_code} from {endpoint}",
        }

    def _publish_direct_sde(self) -> dict[str, Any]:
        """
        Direct SDE publish — add raster to enterprise mosaic dataset.

        Used in 'current' mode (legacy workflow).  Requires ArcGIS 3D Analyst
        / Mosaic Dataset licenses.
        """
        try:
            import arcpy  # type: ignore
        except ImportError as exc:
            raise MosaicPublishError(
                "ArcPy not available for direct SDE publish."
            ) from exc

        sde_cfg = self.context.cfg.get("sde", {})
        connection_file: str = sde_cfg["connection_file"]
        source_mosaic: str = sde_cfg["source_mosaic"]
        derived_mosaic: str = sde_cfg.get("derived_mosaic", "")
        raster_type: str = sde_cfg.get("raster_type", "Raster Dataset")

        raster_path: str = self.artifacts.get("output_raster_path", "")
        if not raster_path or not os.path.isfile(raster_path):
            raise MosaicPublishError(
                f"Raster not found for SDE publish: {raster_path}"
            )

        source_mosaic_path = os.path.join(connection_file, source_mosaic)

        self.logger.info(
            "[%s] Adding raster to source mosaic: %s", self.name, source_mosaic_path
        )
        arcpy.management.AddRastersToMosaicDataset(
            in_mosaic_dataset=source_mosaic_path,
            raster_type=raster_type,
            input_path=raster_path,
            update_cellsize_ranges="UPDATE_CELL_SIZES",
            update_boundary="UPDATE_BOUNDARY",
            update_overviews="NO_OVERVIEWS",
            duplicate_items_action="OVERWRITE_DUPLICATES",
        )

        # Rebuild overview if derived mosaic is configured
        if derived_mosaic:
            derived_path = os.path.join(connection_file, derived_mosaic)
            self.logger.info(
                "[%s] Synchronising derived mosaic: %s", self.name, derived_path
            )
            arcpy.management.SynchronizeMosaicDataset(
                in_mosaic_dataset=derived_path,
                where_clause="",
                new_items=True,
                sync_only_stale=True,
                update_cellsize_ranges=True,
                update_boundary=True,
                update_overviews=False,
            )

        self.logger.info(
            "[%s] Direct SDE publish complete for site %s",
            self.name,
            self.context.site,
        )
        return {
            "publish_status": "direct_published",
            "publish_detail": f"Added to {source_mosaic_path}",
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _integration_mode(self) -> str:
        return (
            self.context.cfg.get("mosaic_publisher", {}).get(
                "integration_mode", "file_trigger"
            )
        )

    def _api_endpoint(self) -> str:
        return self.context.cfg.get("mosaic_publisher", {}).get("api_endpoint", "")
