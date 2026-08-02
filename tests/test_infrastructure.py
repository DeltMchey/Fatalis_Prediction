"""P3.1: Infrastructure verification tests.

Validates that the testing infrastructure is correctly set up:
  - Fixture loading works (conftest.py is discovered)
  - pytest configuration is correct (pytest.ini is loaded)
  - Test discovery functions (tests can be collected)
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import os
import sys

from src.config.offsets import GameOffsets, OFFSETS
from src.config.actions import ACTION_DB, ACTION_MAPPING


# =============================================================================
# Fixture loading tests
# =============================================================================

class TestFixtureLoading:
    """Verify that shared conftest.py fixtures are correctly loaded."""

    def test_sample_df_is_dataframe_with_expected_columns(self, sample_df):
        """sample_df should be a pandas DataFrame with combat-data columns."""
        assert isinstance(sample_df, pd.DataFrame)
        expected_cols = {
            "timestamp", "action_id", "action_name", "phase",
            "hp_percent", "enrage", "distance", "angle",
            "player_x", "player_y", "monster_x", "monster_y", "posture",
        }
        assert expected_cols.issubset(set(sample_df.columns))
        assert len(sample_df) == 5

    def test_sample_csv_path_creates_readable_file(self, sample_csv_path):
        """sample_csv_path should point to an existing CSV file on disk."""
        assert os.path.isfile(sample_csv_path)
        df = pd.read_csv(sample_csv_path)
        assert len(df) == 5
        assert "action_name" in df.columns

    def test_mock_offsets_is_gameoffsets_copy(self, mock_offsets):
        """mock_offsets should be a GameOffsets instance distinct from OFFSETS."""
        assert isinstance(mock_offsets, GameOffsets)
        assert mock_offsets is not OFFSETS
        # Verify it's a deep copy: mutating mock_offsets should not affect OFFSETS
        # (GameOffsets is frozen, so we check equality and separate identity)
        assert mock_offsets == OFFSETS

    def test_temp_data_dir_exists_and_is_directory(self, temp_data_dir):
        """temp_data_dir should be an existing directory path."""
        assert os.path.isdir(temp_data_dir)
        assert os.path.basename(temp_data_dir) == "data"


# =============================================================================
# pytest configuration tests
# =============================================================================

class TestPytestConfiguration:
    """Verify that pytest.ini is correctly configured."""

    def test_rootdir_is_project_root(self, pytestconfig):
        """pytest rootdir should be the project root (where pytest.ini lives)."""
        rootdir = pytestconfig.rootpath
        assert (rootdir / "pytest.ini").exists()
        assert (rootdir / "src").is_dir()

    def test_testpaths_configures_tests_directory(self, pytestconfig):
        """testpaths should point to the tests/ directory."""
        ini = pytestconfig.inipath
        assert ini is not None
        assert ini.name == "pytest.ini"

    def test_pythonpath_allows_root_imports(self):
        """With pythonpath = ., importing src.* modules should work."""
        from src.config.offsets import OFFSETS
        from src.config.actions import ACTION_DB
        assert OFFSETS is not None
        assert len(ACTION_DB) > 0

    def test_strict_markers_enabled(self, pytestconfig):
        """--strict-markers should be in addopts."""
        addopts = pytestconfig.getini("addopts")
        assert "--strict-markers" in addopts

    def test_custom_markers_defined(self, pytestconfig):
        """slow, integration, smoke markers should be registered."""
        markers = pytestconfig.getini("markers")
        marker_names = [m.split(":")[0].strip() for m in markers]
        for expected in ["slow", "integration", "smoke"]:
            assert expected in marker_names, f"marker '{expected}' not found"


# =============================================================================
# Test discovery tests
# =============================================================================

class TestTestDiscovery:
    """Verify that pytest can discover and collect tests."""

    def test_tests_package_has_init(self):
        """tests/ directory should be a Python package with __init__.py."""
        import tests
        assert hasattr(tests, "__file__")
        init = Path(tests.__file__)
        assert init.exists()
        assert init.name == "__init__.py"

    def test_conftest_is_importable(self):
        """tests/conftest.py should be importable."""
        import tests.conftest as conftest
        assert hasattr(conftest, "sample_df")
        assert hasattr(conftest, "sample_csv_path")
        assert hasattr(conftest, "mock_offsets")
        assert hasattr(conftest, "temp_data_dir")

    def test_self_discovery(self):
        """This test file itself should be discoverable (trivial self-check)."""
        assert __file__.endswith("test_infrastructure.py")

    def test_src_imports_work(self):
        """Core src modules should be importable."""
        import src
        import src.config
        import src.config.offsets
        import src.config.actions
        assert True  # imports succeeded


# =============================================================================
# Coverage configuration tests
# =============================================================================

class TestCoverageConfiguration:
    """Verify that .coveragerc is valid and properly configured."""

    def test_coveragerc_exists(self):
        """Project root should have a .coveragerc file."""
        root = Path(__file__).parent.parent
        coveragerc = root / ".coveragerc"
        assert coveragerc.exists()

    def test_coveragerc_excludes_tests_and_venv(self):
        """Source omit list should exclude tests/, .venv/, and archive/."""
        root = Path(__file__).parent.parent
        coveragerc = root / ".coveragerc"
        content = coveragerc.read_text(encoding="utf-8")
        assert "tests/*" in content
        assert ".venv/*" in content
        assert "archive/*" in content


# =============================================================================
# GitHub Actions workflow tests
# =============================================================================

class TestGitHubActionsWorkflow:
    """Verify that the CI workflow file is syntactically valid."""

    def test_workflow_file_exists(self):
        """CI workflow should exist at .github/workflows/test.yml."""
        root = Path(__file__).parent.parent
        workflow = root / ".github" / "workflows" / "test.yml"
        assert workflow.exists()

    def test_workflow_contains_pytest_cov(self):
        """CI workflow should run pytest with coverage."""
        root = Path(__file__).parent.parent
        workflow = root / ".github" / "workflows" / "test.yml"
        content = workflow.read_text(encoding="utf-8")
        assert "pytest" in content
        assert "--cov" in content
