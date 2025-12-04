"""Tests for predefined workflow templates."""

import pytest

from agentsh.workflows.predefined import (
    AVAILABLE_WORKFLOWS,
    get_workflow_info,
    list_predefined_workflows,
    load_workflow_template,
    validate_workflow_parameters,
)


class TestListPredefinedWorkflows:
    """Test listing predefined workflows."""

    def test_lists_available_workflows(self) -> None:
        """Should list all available workflows."""
        workflows = list_predefined_workflows()

        assert "bootstrap" in workflows
        assert "backup" in workflows
        assert "deploy" in workflows

    def test_workflows_are_sorted(self) -> None:
        """Should return sorted list."""
        workflows = list_predefined_workflows()

        assert workflows == sorted(workflows)


class TestLoadWorkflowTemplate:
    """Test loading workflow templates."""

    def test_loads_bootstrap_workflow(self) -> None:
        """Should load bootstrap workflow."""
        workflow = load_workflow_template("bootstrap")

        assert workflow is not None
        assert workflow["name"] == "project_bootstrap"
        assert "parameters" in workflow
        assert "steps" in workflow

    def test_loads_backup_workflow(self) -> None:
        """Should load backup workflow."""
        workflow = load_workflow_template("backup")

        assert workflow is not None
        assert workflow["name"] == "directory_backup"

    def test_loads_deploy_workflow(self) -> None:
        """Should load deploy workflow."""
        workflow = load_workflow_template("deploy")

        assert workflow is not None
        assert workflow["name"] == "application_deploy"

    def test_returns_none_for_unknown(self) -> None:
        """Should return None for unknown workflow."""
        workflow = load_workflow_template("nonexistent_workflow")

        assert workflow is None


class TestGetWorkflowInfo:
    """Test getting workflow information."""

    def test_gets_bootstrap_info(self) -> None:
        """Should get bootstrap workflow info."""
        info = get_workflow_info("bootstrap")

        assert info is not None
        assert info["name"] == "project_bootstrap"
        assert "description" in info
        assert "parameters" in info
        assert info["steps"] > 0

    def test_gets_backup_info(self) -> None:
        """Should get backup workflow info."""
        info = get_workflow_info("backup")

        assert info is not None
        assert "source_path" in info["parameters"]

    def test_returns_none_for_unknown(self) -> None:
        """Should return None for unknown workflow."""
        info = get_workflow_info("unknown")

        assert info is None


class TestValidateWorkflowParameters:
    """Test workflow parameter validation."""

    def test_validates_bootstrap_params(self) -> None:
        """Should validate bootstrap parameters."""
        params = {
            "project_type": "python",
            "project_name": "myproject",
        }

        valid, errors = validate_workflow_parameters("bootstrap", params)

        assert valid is True
        assert errors == []

    def test_rejects_missing_required(self) -> None:
        """Should reject missing required parameters."""
        params = {
            "project_type": "python",
            # Missing project_name
        }

        valid, errors = validate_workflow_parameters("bootstrap", params)

        assert valid is False
        assert any("project_name" in e for e in errors)

    def test_rejects_invalid_enum(self) -> None:
        """Should reject invalid enum values."""
        params = {
            "project_type": "invalid_type",
            "project_name": "test",
        }

        valid, errors = validate_workflow_parameters("bootstrap", params)

        assert valid is False
        assert any("project_type" in e for e in errors)

    def test_rejects_wrong_type(self) -> None:
        """Should reject wrong parameter types."""
        params = {
            "source_path": "/path/to/backup",
            "compress": "yes",  # Should be boolean
        }

        valid, errors = validate_workflow_parameters("backup", params)

        assert valid is False
        assert any("compress" in e for e in errors)

    def test_returns_error_for_unknown_workflow(self) -> None:
        """Should return error for unknown workflow."""
        valid, errors = validate_workflow_parameters("unknown", {})

        assert valid is False
        assert any("not found" in e for e in errors)


class TestAvailableWorkflows:
    """Test AVAILABLE_WORKFLOWS constant."""

    def test_has_expected_workflows(self) -> None:
        """Should have all expected workflows."""
        assert "bootstrap" in AVAILABLE_WORKFLOWS
        assert "backup" in AVAILABLE_WORKFLOWS
        assert "deploy" in AVAILABLE_WORKFLOWS

    def test_has_descriptions(self) -> None:
        """Should have descriptions for all workflows."""
        for name, description in AVAILABLE_WORKFLOWS.items():
            assert isinstance(description, str)
            assert len(description) > 0
