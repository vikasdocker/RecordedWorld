"""Tests for Phase 29: MVP Definition — validation, status, readiness."""

import pytest
from app.services.mvp_config import (
    MVP_COMPONENTS, get_mvp_status, validate_mvp_readiness, MVPComponent,
)


class TestMVPComponents:
    def test_components_exist(self):
        """MVP components are defined."""
        assert len(MVP_COMPONENTS) > 0

    def test_components_have_names(self):
        """All components have names."""
        for c in MVP_COMPONENTS:
            assert c.name is not None
            assert len(c.name) > 0

    def test_components_have_phases(self):
        """All components have phase numbers."""
        for c in MVP_COMPONENTS:
            assert c.phase > 0

    def test_components_have_status(self):
        """All components have valid status."""
        valid = {"complete", "partial", "missing"}
        for c in MVP_COMPONENTS:
            assert c.status in valid


class TestMVPStatus:
    def test_get_status(self):
        """Can get MVP status."""
        status = get_mvp_status()
        assert "total_components" in status
        assert "complete" in status
        assert "completion_percent" in status

    def test_completion_percent(self):
        """Completion percent is calculated."""
        status = get_mvp_status()
        assert 0 <= status["completion_percent"] <= 100

    def test_all_complete(self):
        """All components should be complete or partial (no missing)."""
        status = get_mvp_status()
        assert status["missing"] == 0


class TestMVPValidation:
    def test_validate_readiness(self):
        """Can validate MVP readiness."""
        result = validate_mvp_readiness()
        assert "ready" in result
        assert "readiness_score" in result

    def test_readiness_score(self):
        """Readiness score is calculated."""
        result = validate_mvp_readiness()
        assert 0 <= result["readiness_score"] <= 100

    def test_no_missing_components(self):
        """No components should be missing."""
        result = validate_mvp_readiness()
        missing = [i for i in result["issues"] if i.startswith("MISSING")]
        assert len(missing) == 0


class TestMVPCoverage:
    def test_geospatial_covered(self):
        """Geospatial is covered."""
        names = [c.name for c in MVP_COMPONENTS]
        assert any("Geospatial" in n for n in names)

    def test_multiplayer_covered(self):
        """Multiplayer is covered."""
        names = [c.name for c in MVP_COMPONENTS]
        assert any("Multiplayer" in n for n in names)

    def test_security_covered(self):
        """Security is covered."""
        names = [c.name for c in MVP_COMPONENTS]
        assert any("Security" in n for n in names)
