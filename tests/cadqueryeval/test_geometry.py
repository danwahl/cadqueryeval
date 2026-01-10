"""Tests for geometry checking functions.

Note: These tests require the optional scorer dependencies (open3d, trimesh).
Run with: pytest tests/cadqueryeval/test_geometry.py
"""

import pytest

from cadqueryeval.dataset import get_reference_stl_path

# Mark all tests in this module as requiring scorer dependencies
pytestmark = pytest.mark.skipif(
    True,  # Will be changed when we can detect open3d
    reason="Requires scorer dependencies (open3d, trimesh)",
)


try:
    import open3d  # noqa: F401
    import trimesh  # noqa: F401

    from cadqueryeval.geometry import (
        GeometryCheckResult,
        check_single_component,
        check_volume,
        check_watertight,
        perform_geometry_checks,
    )

    # Re-enable tests if imports succeed
    pytestmark = pytest.mark.skipif(False, reason="")

except ImportError:
    pass


class TestWatertightCheck:
    """Tests for watertight checking."""

    def test_reference_stl_is_watertight(self):
        """Reference STLs should be watertight."""
        stl_path = get_reference_stl_path("task1")
        is_watertight, error = check_watertight(stl_path)
        assert is_watertight is True
        assert error is None

    def test_nonexistent_file(self):
        """Test handling of missing file."""
        is_watertight, error = check_watertight("/nonexistent/file.stl")
        assert is_watertight is False
        assert "not found" in error.lower()


class TestComponentCheck:
    """Tests for component counting."""

    def test_reference_stl_single_component(self):
        """Reference STLs should have expected component count."""
        stl_path = get_reference_stl_path("task1")
        is_single, error = check_single_component(stl_path, expected_components=1)
        assert is_single is True
        assert error is None


class TestVolumeCheck:
    """Tests for volume comparison."""

    def test_same_file_passes(self):
        """Same file compared to itself should pass."""
        stl_path = get_reference_stl_path("task1")
        passed, ref_vol, gen_vol, error = check_volume(stl_path, stl_path)
        assert passed
        assert ref_vol == gen_vol
        assert error is None


class TestGeometryCheckResult:
    """Tests for GeometryCheckResult dataclass."""

    def test_all_passed_true(self):
        """Test all_passed when everything passes."""
        result = GeometryCheckResult(
            is_watertight=True,
            is_single_component=True,
            bbox_accurate=True,
            volume_passed=True,
            chamfer_passed=True,
            hausdorff_passed=True,
        )
        assert result.all_passed is True

    def test_all_passed_false_on_failure(self):
        """Test all_passed when one check fails."""
        result = GeometryCheckResult(
            is_watertight=True,
            is_single_component=True,
            bbox_accurate=False,  # Failed
            volume_passed=True,
            chamfer_passed=True,
            hausdorff_passed=True,
        )
        assert result.all_passed is False

    def test_all_passed_false_on_none(self):
        """Test all_passed when a check is None."""
        result = GeometryCheckResult(
            is_watertight=True,
            is_single_component=True,
            bbox_accurate=None,  # Not run
            volume_passed=True,
            chamfer_passed=True,
            hausdorff_passed=True,
        )
        assert result.all_passed is False


class TestPerformGeometryChecks:
    """Tests for the main geometry check orchestrator."""

    def test_same_file_all_pass(self):
        """Comparing a file to itself should pass all checks."""
        stl_path = str(get_reference_stl_path("task1"))
        result = perform_geometry_checks(
            generated_path=stl_path,
            reference_path=stl_path,
        )
        assert result.is_watertight is True
        assert result.is_single_component is True
        # Same file should have perfect similarity
        assert result.chamfer_distance is not None
        assert result.chamfer_distance < 0.2  # Nearly zero (relaxed for RANSAC noise)

    def test_missing_generated_file(self):
        """Test handling of missing generated file."""
        result = perform_geometry_checks(
            generated_path="/nonexistent/file.stl",
            reference_path=str(get_reference_stl_path("task1")),
        )
        assert result.errors is not None
        assert len(result.errors) > 0
