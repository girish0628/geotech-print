"""Custom exceptions for the FMS pipeline."""


class ConfigLoadError(Exception):
    """Raised when configuration loading fails."""


class ArcPyExecutionError(Exception):
    """Raised when an ArcPy operation fails."""


class FMEWebhookError(Exception):
    """Raised when an FME Flow webhook call fails."""


class ValidationError(Exception):
    """Raised when input validation fails."""


class SnippetParseError(Exception):
    """Raised when a Minestar snippet file cannot be parsed."""


class ElevationProcessingError(Exception):
    """Raised when raster/TIN generation fails."""


class SurfacePackageError(Exception):
    """Raised when building the surface output package fails."""


class MosaicPublishError(Exception):
    """Raised when handing off to the mosaic publisher fails."""


class PipelineStepError(Exception):
    """Raised when a pipeline step fails in validate() or execute()."""

    def __init__(self, step_name: str, message: str) -> None:
        super().__init__(f"[{step_name}] {message}")
        self.step_name = step_name
