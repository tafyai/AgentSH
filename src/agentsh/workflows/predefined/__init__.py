"""Predefined workflow templates."""

import os
from pathlib import Path
from typing import Any, Optional

import yaml

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)

# Directory containing predefined workflows
PREDEFINED_DIR = Path(__file__).parent


def list_predefined_workflows() -> list[str]:
    """List available predefined workflows.

    Returns:
        List of workflow names (without .yaml extension)
    """
    workflows = []
    for file in PREDEFINED_DIR.glob("*.yaml"):
        workflows.append(file.stem)
    return sorted(workflows)


def load_workflow_template(name: str) -> Optional[dict[str, Any]]:
    """Load a predefined workflow template.

    Args:
        name: Workflow name (without .yaml extension)

    Returns:
        Workflow definition dict or None if not found
    """
    workflow_path = PREDEFINED_DIR / f"{name}.yaml"

    if not workflow_path.exists():
        logger.warning("Workflow not found", name=name)
        return None

    try:
        with open(workflow_path, "r") as f:
            workflow = yaml.safe_load(f)

        logger.debug("Loaded workflow template", name=name)
        return workflow

    except yaml.YAMLError as e:
        logger.error("Failed to parse workflow", name=name, error=str(e))
        return None
    except Exception as e:
        logger.error("Failed to load workflow", name=name, error=str(e))
        return None


def get_workflow_info(name: str) -> Optional[dict[str, Any]]:
    """Get information about a predefined workflow.

    Args:
        name: Workflow name

    Returns:
        Dict with name, description, parameters, etc.
    """
    workflow = load_workflow_template(name)
    if not workflow:
        return None

    return {
        "name": workflow.get("name", name),
        "description": workflow.get("description", ""),
        "version": workflow.get("version", "1.0"),
        "parameters": workflow.get("parameters", {}),
        "steps": len(workflow.get("steps", [])),
    }


def validate_workflow_parameters(
    name: str,
    params: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Validate parameters for a workflow.

    Args:
        name: Workflow name
        params: Parameters to validate

    Returns:
        Tuple of (valid, list of error messages)
    """
    workflow = load_workflow_template(name)
    if not workflow:
        return False, [f"Workflow '{name}' not found"]

    errors = []
    param_defs = workflow.get("parameters", {})

    # Check required parameters
    for param_name, param_def in param_defs.items():
        if param_def.get("required", False) and param_name not in params:
            errors.append(f"Missing required parameter: {param_name}")

        # Check enum values
        if param_name in params:
            value = params[param_name]
            if "enum" in param_def and value not in param_def["enum"]:
                errors.append(
                    f"Invalid value for {param_name}: {value}. "
                    f"Must be one of: {param_def['enum']}"
                )

            # Check type
            expected_type = param_def.get("type")
            if expected_type:
                type_map = {
                    "string": str,
                    "integer": int,
                    "boolean": bool,
                    "number": (int, float),
                }
                python_type = type_map.get(expected_type)
                if python_type and not isinstance(value, python_type):
                    errors.append(
                        f"Invalid type for {param_name}: expected {expected_type}"
                    )

    return len(errors) == 0, errors


# Available workflows
AVAILABLE_WORKFLOWS = {
    "bootstrap": "Set up a new project environment",
    "backup": "Create a timestamped backup of a directory",
    "deploy": "Deploy an application with pre-checks and verification",
}
