"""Unit tests for SceneChangeService (NEM-3555)."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.models.scene_change import SceneChangeType
from backend.services.scene_change_service import (
    SceneChangeService,
    classify_scene_change_type,
)


class TestClassifySceneChangeType:
    """Tests for classify_scene_change_type function."""

    def test_very_low_score_is_view_blocked(self) -> None:
        assert classify_scene_change_type(0.0) == SceneChangeType.VIEW_BLOCKED
        assert classify_scene_change_type(0.29) == SceneChangeType.VIEW_BLOCKED

    def test_low_score_is_view_tampered(self) -> None:
        assert classify_scene_change_type(0.3) == SceneChangeType.VIEW_TAMPERED
        assert classify_scene_change_type(0.49) == SceneChangeType.VIEW_TAMPERED

    def test_medium_score_is_angle_changed(self) -> None:
        assert classify_scene_change_type(0.5) == SceneChangeType.ANGLE_CHANGED
        assert classify_scene_change_type(0.69) == SceneChangeType.ANGLE_CHANGED

    def test_high_score_is_unknown(self) -> None:
        assert classify_scene_change_type(0.7) == SceneChangeType.UNKNOWN
        assert classify_scene_change_type(0.89) == SceneChangeType.UNKNOWN


class TestSceneChangeServiceInit:
    """Tests for SceneChangeService initialization."""

    def test_init_with_session_only(self) -> None:
        mock_session = MagicMock()
        service = SceneChangeService(mock_session)
        assert service._session is mock_session
        assert service._emitter is None

    def test_init_with_emitter(self) -> None:
        mock_session = MagicMock()
        mock_emitter = MagicMock()
        service = SceneChangeService(mock_session, mock_emitter)
        assert service._session is mock_session
        assert service._emitter is mock_emitter
