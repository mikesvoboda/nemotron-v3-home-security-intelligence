"""Batch-14 battery: job_service tracker lookup arg identity (C9)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.models.job import JobStatus
from backend.services.job_service import JobService

pytestmark = pytest.mark.unit


class TestTrackerIdArg:
    """C9: get_job_or_404/get_job_detail passing None to the tracker."""

    @pytest.fixture
    def tracker(self):
        from backend.services.job_tracker import JobTracker

        t = MagicMock(spec=JobTracker)
        t.get_job_from_redis = AsyncMock()
        return t

    def test_or_404_forwards_exact_id(self, tracker):
        info = {
            "job_id": "id-77",
            "job_type": "export",
            "status": JobStatus.RUNNING,
            "progress": 0,
            "message": "",
            "created_at": "2024-01-15T10:30:00+00:00",
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        tracker.get_job.return_value = info
        svc = JobService(job_tracker=tracker, redis_client=MagicMock())
        assert svc.get_job_or_404("id-77") is info
        tracker.get_job.assert_called_once_with("id-77")

    async def test_detail_forwards_exact_id(self, tracker):
        svc = JobService(job_tracker=tracker, redis_client=MagicMock())
        tracker.get_job.return_value = None
        tracker.get_job_from_redis.return_value = None
        with pytest.raises(HTTPException) as ei:
            await svc.get_job_detail("id-88")
        assert ei.value.status_code == 404
        tracker.get_job.assert_called_once_with("id-88")
        tracker.get_job_from_redis.assert_awaited_once_with("id-88")
