"""Abstract base class for all FMS pipeline steps."""
from __future__ import annotations

import abc
from typing import Any

from src.core.context import ExecutionContext
from src.core.exceptions import PipelineStepError
from src.core.logger import get_logger


class BasePipelineStep(abc.ABC):
    """
    Abstract base for every FMS pipeline step.

    Subclasses must implement:
        validate() — check preconditions; raise ValidationError on failure
        execute()  — perform work; return a dict of output artifacts

    The orchestrator injects ``self.artifacts`` (outputs accumulated from all
    prior steps) before calling ``run()``.  Steps access previous outputs via
    ``self.artifacts.get("key")``.

    Dry-run mode: validate() always runs; execute() is skipped.
    """

    def __init__(self, context: ExecutionContext) -> None:
        self.context = context
        # Injected by PipelineOrchestrator before run() is called
        self.artifacts: dict[str, Any] = {}
        self.logger = get_logger(self.__class__.__module__)

    @property
    def name(self) -> str:
        """Human-readable step name used in log messages."""
        return self.__class__.__name__

    @abc.abstractmethod
    def validate(self) -> None:
        """
        Assert that all preconditions for this step are satisfied.

        Raises
        ------
        ValidationError
            If any precondition is not met.
        """
        ...

    @abc.abstractmethod
    def execute(self) -> dict[str, Any]:
        """
        Perform the step's work.

        Returns
        -------
        dict[str, Any]
            Output artifacts forwarded to subsequent steps.
        """
        ...

    def run(self) -> dict[str, Any]:
        """
        Orchestrate validate → execute with dry-run and error wrapping.

        Returns
        -------
        dict[str, Any]
            Output artifacts from this step (empty dict in dry-run mode).

        Raises
        ------
        PipelineStepError
            Wraps any exception raised by validate() or execute().
        """
        self.logger.info("[%s] Validating...", self.name)
        try:
            self.validate()
        except Exception as exc:
            raise PipelineStepError(self.name, f"Validation failed: {exc}") from exc

        if self.context.dry_run:
            self.logger.info("[%s] DryRun — skipping execute()", self.name)
            return {}

        self.logger.info("[%s] Executing...", self.name)
        try:
            result = self.execute()
        except PipelineStepError:
            raise
        except Exception as exc:
            raise PipelineStepError(self.name, f"Execution failed: {exc}") from exc

        self.logger.info("[%s] Complete", self.name)
        return result or {}
