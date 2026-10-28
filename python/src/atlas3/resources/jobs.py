"""Background job inspection and polling."""

from __future__ import annotations

import time
from typing import Any, List

from ..models import Job, Page
from .base import Resource, page_from


class JobTimeoutError(TimeoutError):
    """A WebAPI job did not finish before the requested timeout."""


class JobsResource(Resource):
    """Inspect and wait for WebAPI background jobs."""

    def list(
        self,
        *,
        job_name: str | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> Page[Job]:
        """List job executions, optionally filtered by job name."""
        payload = self._get(
            "/job/execution",
            params={"jobName": job_name, "page": page, "size": size},
        )
        if isinstance(payload, list):
            return Page[Job](
                content=[Job.model_validate(item) for item in payload],
                totalElements=len(payload),
                totalPages=1,
                number=0,
                size=len(payload),
            )
        return page_from(payload)

    def get(self, job_id: int) -> dict[str, Any]:
        """Return a job instance by ID."""
        return self._get(f"/job/{job_id}") or {}

    def execution(self, execution_id: int) -> Job:
        """Return a job execution by ID."""
        return Job.model_validate(self._get(f"/job/execution/{execution_id}"))

    def by_name(self, job_type: str, job_name: str) -> Job:
        """Find a job execution by type and name."""
        return Job.model_validate(self._get(f"/job/type/{job_type}/name/{job_name}"))

    def names(self) -> List[str]:
        """List registered job names."""
        return self._get("/job") or []

    def wait(
        self,
        job: Job | int,
        *,
        timeout: float = 600.0,
        poll_interval: float = 2.0,
        raise_on_failure: bool = True,
    ) -> Job:
        """Poll an execution until it finishes.

        Args:
            job: A :class:`Job` returned by ``generate`` or an execution ID.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls.
            raise_on_failure: Raise :class:`RuntimeError` when the job did not
                complete successfully.

        Raises:
            JobTimeoutError: If the job is still running at ``timeout``.
            RuntimeError: If the job failed and ``raise_on_failure`` is true.
        """
        execution_id = job.execution_id if isinstance(job, Job) else int(job)
        if execution_id is None:
            raise ValueError("Job has no executionId; cannot poll it")
        deadline = time.monotonic() + timeout
        latest = job if isinstance(job, Job) else self.execution(execution_id)
        while not latest.finished:
            if time.monotonic() >= deadline:
                raise JobTimeoutError(
                    f"Job execution {execution_id} did not finish within {timeout:.0f}s "
                    f"(last status: {latest.status!r})"
                )
            time.sleep(poll_interval)
            latest = self.execution(execution_id)
        if raise_on_failure and not latest.succeeded:
            raise RuntimeError(
                f"Job execution {execution_id} finished with status {latest.status!r} "
                f"and exit status {latest.exit_status!r}: {latest.fail_message or ''}".strip()
            )
        return latest
