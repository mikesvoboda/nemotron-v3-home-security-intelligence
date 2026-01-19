"""Background jobs for the security monitoring system.

This package contains background jobs that run periodically or on-demand
to maintain system health and data integrity.

Jobs:
    - TimeoutCheckerJob: Checks for timed-out processing jobs
    - OrphanCleanupJob: Periodically scans for and removes orphaned files
    - SummaryJob: Generates hourly and daily dashboard summaries
"""

from .orphan_cleanup_job import CleanupReport, OrphanCleanupJob
from .summary_job import (
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_TIMEOUT_SECONDS,
    JOB_TYPE_GENERATE_SUMMARIES,
    SummaryJob,
    SummaryJobScheduler,
    get_summary_job_scheduler,
    reset_summary_job_scheduler,
)
from .timeout_checker_job import (
    DEFAULT_CHECK_INTERVAL_SECONDS,
    TimeoutCheckerJob,
    get_timeout_checker_job,
    reset_timeout_checker_job,
)

__all__ = [
    "DEFAULT_CHECK_INTERVAL_SECONDS",
    "DEFAULT_INTERVAL_MINUTES",
    "DEFAULT_TIMEOUT_SECONDS",
    "JOB_TYPE_GENERATE_SUMMARIES",
    "CleanupReport",
    "OrphanCleanupJob",
    "SummaryJob",
    "SummaryJobScheduler",
    "TimeoutCheckerJob",
    "get_summary_job_scheduler",
    "get_timeout_checker_job",
    "reset_summary_job_scheduler",
    "reset_timeout_checker_job",
]
