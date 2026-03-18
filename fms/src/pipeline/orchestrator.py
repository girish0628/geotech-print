"""FMS pipeline orchestrator — runs steps in sequence, threads artifacts."""
from __future__ import annotations

from typing import Any

from src.core.context import ExecutionContext
from src.core.logger import get_logger
from src.pipeline.base_step import BasePipelineStep


class PipelineOrchestrator:
    """
    Runs a list of BasePipelineStep instances in declared order.

    After each step executes, its return dict is merged into ``accumulated``.
    The next step receives a copy of ``accumulated`` as its ``artifacts``
    attribute, giving it read access to all prior step outputs.

    Parameters
    ----------
    context : ExecutionContext
        Shared runtime context for the pipeline run.
    steps : list[BasePipelineStep]
        Ordered list of steps to execute.
    """

    def __init__(
        self, context: ExecutionContext, steps: list[BasePipelineStep]
    ) -> None:
        self.context = context
        self.steps = steps
        self.logger = get_logger(__name__)

    def run(self) -> dict[str, Any]:
        """
        Execute all steps in order.

        Returns
        -------
        dict[str, Any]
            Merged output artifacts from every step.

        Raises
        ------
        PipelineStepError
            Re-raised from the failing step — halts the pipeline immediately.
        """
        accumulated: dict[str, Any] = {}

        _SEP = "=" * 70
        self.logger.info(_SEP)
        self.logger.info(
            "FMS Pipeline  |  Site: %s  |  Run: %s  |  Env: %s  |  Source: %s  |  DryRun: %s",
            self.context.site,
            self.context.run_timestamp,
            self.context.env,
            self.context.source_type,
            self.context.dry_run,
        )
        self.logger.info(_SEP)

        for step in self.steps:
            step.artifacts = accumulated.copy()
            result = step.run()
            accumulated.update(result)

        self.logger.info(_SEP)
        self.logger.info(
            "FMS Pipeline Complete  |  Site: %s  |  Run: %s",
            self.context.site,
            self.context.run_timestamp,
        )
        self.logger.info(_SEP)

        return accumulated
