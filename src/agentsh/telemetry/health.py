"""Health checks for AgentSH components."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class HealthStatus(str, Enum):
    """Health status values."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthResult:
    """Result of a health check."""

    healthy: bool
    status: HealthStatus
    message: Optional[str] = None
    details: Optional[dict] = None


class HealthChecker:
    """Performs health checks on AgentSH components."""

    def check_shell(self) -> HealthResult:
        """Check if shell/PTY is healthy."""
        # Placeholder - will be implemented in Phase 1
        return HealthResult(
            healthy=True,
            status=HealthStatus.UNKNOWN,
            message="Shell check not yet implemented",
        )

    def check_llm(self) -> HealthResult:
        """Check if LLM connection is healthy."""
        # Placeholder - will be implemented in Phase 2
        return HealthResult(
            healthy=True,
            status=HealthStatus.UNKNOWN,
            message="LLM check not yet implemented",
        )

    def check_memory(self) -> HealthResult:
        """Check if memory store is healthy."""
        # Placeholder - will be implemented in Phase 6
        return HealthResult(
            healthy=True,
            status=HealthStatus.UNKNOWN,
            message="Memory check not yet implemented",
        )

    def check_config(self) -> HealthResult:
        """Check if configuration is valid."""
        try:
            from agentsh.config.loader import load_config

            load_config()
            return HealthResult(
                healthy=True,
                status=HealthStatus.HEALTHY,
                message="Configuration loaded successfully",
            )
        except Exception as e:
            return HealthResult(
                healthy=False,
                status=HealthStatus.UNHEALTHY,
                message=f"Configuration error: {e}",
            )

    def check_all(self) -> dict[str, HealthResult]:
        """Run all health checks.

        Returns:
            Dictionary mapping component name to health result
        """
        return {
            "config": self.check_config(),
            "shell": self.check_shell(),
            "llm": self.check_llm(),
            "memory": self.check_memory(),
        }
