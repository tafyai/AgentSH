"""Configuration schemas using Pydantic for validation."""

from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"


class SecurityMode(str, Enum):
    """Security enforcement modes."""

    STRICT = "strict"  # Block more, require more approvals
    NORMAL = "normal"  # Balanced
    LENIENT = "lenient"  # Fewer restrictions (dangerous)


class MemoryType(str, Enum):
    """Memory storage types."""

    IN_MEMORY = "in_memory"
    PERSISTENT = "persistent"


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: LLMProvider = Field(
        default=LLMProvider.ANTHROPIC,
        description="Primary LLM provider to use",
    )
    model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model name/ID to use",
    )
    api_key_env: str = Field(
        default="ANTHROPIC_API_KEY",
        description="Environment variable containing API key",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: int = Field(
        default=4096,
        gt=0,
        description="Maximum tokens in response",
    )
    fallback_provider: Optional[LLMProvider] = Field(
        default=None,
        description="Fallback provider if primary fails",
    )
    fallback_model: Optional[str] = Field(
        default=None,
        description="Fallback model to use",
    )
    timeout_seconds: int = Field(
        default=60,
        gt=0,
        description="Timeout for LLM API calls",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts for failed calls",
    )


class ShellConfig(BaseModel):
    """Shell wrapper configuration."""

    backend: str = Field(
        default="zsh",
        description="Shell to use (bash, zsh, fish)",
    )
    init_script: Optional[Path] = Field(
        default=None,
        description="Shell init script to source",
    )
    history_size: int = Field(
        default=10000,
        gt=0,
        description="Maximum history entries",
    )
    ai_prefix: str = Field(
        default="ai ",
        description="Prefix to force AI routing",
    )
    shell_prefix: str = Field(
        default="!",
        description="Prefix to force shell routing",
    )
    default_to_ai: bool = Field(
        default=False,
        description="Route unrecognized input to AI (vs shell)",
    )


class SecurityConfig(BaseModel):
    """Security and permission configuration."""

    mode: SecurityMode = Field(
        default=SecurityMode.NORMAL,
        description="Security enforcement mode",
    )
    require_confirmation: bool = Field(
        default=True,
        description="Require confirmation for risky commands",
    )
    allow_autonomous: bool = Field(
        default=False,
        description="Allow agent to execute without approval",
    )
    audit_log_path: Optional[Path] = Field(
        default=None,
        description="Path to audit log file",
    )
    deny_patterns: list[str] = Field(
        default_factory=lambda: [
            r"^rm\s+-rf\s+/$",
            r"^mkfs\.",
            r"^dd\s+if=.*of=/dev",
            r":()\{\s*:\|:&\s*\};:",
        ],
        description="Regex patterns to always block",
    )
    max_command_length: int = Field(
        default=10000,
        gt=0,
        description="Maximum command length to execute",
    )
    approval_timeout_seconds: int = Field(
        default=60,
        gt=0,
        description="Timeout for approval prompts",
    )


class MemoryConfig(BaseModel):
    """Memory and context configuration."""

    type: MemoryType = Field(
        default=MemoryType.PERSISTENT,
        description="Memory storage type",
    )
    db_path: Optional[Path] = Field(
        default=None,
        description="Path to memory database",
    )
    session_max_entries: int = Field(
        default=100,
        gt=0,
        description="Maximum session history entries",
    )
    enable_semantic_search: bool = Field(
        default=False,
        description="Enable vector-based semantic search",
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Model for generating embeddings",
    )
    retention_days: dict[str, int] = Field(
        default_factory=lambda: {
            "configuration": 730,
            "incident": 365,
            "interaction": 90,
        },
        description="Retention periods by memory type",
    )


class TelemetryConfig(BaseModel):
    """Telemetry and monitoring configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable telemetry collection",
    )
    log_file: Optional[Path] = Field(
        default=None,
        description="Path to log file",
    )
    metrics_enabled: bool = Field(
        default=False,
        description="Enable Prometheus metrics",
    )
    metrics_port: int = Field(
        default=9090,
        gt=0,
        lt=65536,
        description="Port for metrics endpoint",
    )
    health_check_interval_seconds: int = Field(
        default=60,
        gt=0,
        description="Interval between health checks",
    )


class MCPServerConfig(BaseModel):
    """MCP server configuration."""

    enabled: bool = Field(
        default=False,
        description="Enable MCP server",
    )
    port: int = Field(
        default=9999,
        gt=0,
        lt=65536,
        description="Port for MCP server",
    )
    auth_token_env: str = Field(
        default="AGENTSH_MCP_TOKEN",
        description="Environment variable for auth token",
    )


class OrchestratorConfig(BaseModel):
    """Multi-device orchestration configuration."""

    enabled: bool = Field(
        default=False,
        description="Enable multi-device orchestration",
    )
    devices_file: Optional[Path] = Field(
        default=None,
        description="Path to devices inventory file",
    )
    ssh_timeout: int = Field(
        default=30,
        gt=0,
        description="SSH connection timeout",
    )
    max_parallel_connections: int = Field(
        default=10,
        gt=0,
        description="Maximum concurrent SSH connections",
    )
    mcp_server: MCPServerConfig = Field(
        default_factory=MCPServerConfig,
        description="MCP server configuration",
    )


class PluginConfig(BaseModel):
    """Plugin configuration."""

    name: str = Field(
        description="Plugin name",
    )
    enabled: bool = Field(
        default=True,
        description="Whether plugin is enabled",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Plugin-specific configuration",
    )


class AgentSHConfig(BaseModel):
    """Root configuration for AgentSH."""

    llm: LLMConfig = Field(
        default_factory=LLMConfig,
        description="LLM provider configuration",
    )
    shell: ShellConfig = Field(
        default_factory=ShellConfig,
        description="Shell wrapper configuration",
    )
    security: SecurityConfig = Field(
        default_factory=SecurityConfig,
        description="Security configuration",
    )
    memory: MemoryConfig = Field(
        default_factory=MemoryConfig,
        description="Memory configuration",
    )
    telemetry: TelemetryConfig = Field(
        default_factory=TelemetryConfig,
        description="Telemetry configuration",
    )
    orchestrator: OrchestratorConfig = Field(
        default_factory=OrchestratorConfig,
        description="Orchestration configuration",
    )
    plugins: list[PluginConfig] = Field(
        default_factory=lambda: [
            PluginConfig(name="shell", enabled=True),
            PluginConfig(name="filesystem", enabled=True),
            PluginConfig(name="process", enabled=True),
            PluginConfig(name="code", enabled=True),
        ],
        description="Plugin configurations",
    )
    log_level: str = Field(
        default="INFO",
        description="Global log level",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()

    def get_plugin_config(self, name: str) -> Optional[PluginConfig]:
        """Get configuration for a specific plugin."""
        for plugin in self.plugins:
            if plugin.name == name:
                return plugin
        return None

    def is_plugin_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        config = self.get_plugin_config(name)
        return config.enabled if config else False
