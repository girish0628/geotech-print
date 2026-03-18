"""Custom exceptions for the application."""


class ConfigLoadError(Exception):
    """Raised when configuration loading fails."""


class ArcPyExecutionError(Exception):
    """Raised when an ArcPy operation fails."""


class FMEWebhookError(Exception):
    """Raised when an FME Flow webhook call fails."""


class ValidationError(Exception):
    """Raised when input validation fails."""
