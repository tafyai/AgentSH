"""Default configuration values for AgentSH."""

from pathlib import Path

# Default paths
DEFAULT_CONFIG_DIR = Path.home() / ".agentsh"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
DEFAULT_HISTORY_FILE = DEFAULT_CONFIG_DIR / "history"
DEFAULT_MEMORY_DB = DEFAULT_CONFIG_DIR / "memory.db"
DEFAULT_AUDIT_LOG = DEFAULT_CONFIG_DIR / "audit.log"
DEFAULT_LOG_FILE = DEFAULT_CONFIG_DIR / "agentsh.log"
DEFAULT_DEVICES_FILE = DEFAULT_CONFIG_DIR / "devices.yaml"
DEFAULT_PLUGINS_DIR = DEFAULT_CONFIG_DIR / "plugins"

# Default shell settings
DEFAULT_SHELL = "zsh"
DEFAULT_HISTORY_SIZE = 10000
DEFAULT_AI_PREFIX = "ai "
DEFAULT_SHELL_PREFIX = "!"

# Default LLM settings
DEFAULT_LLM_PROVIDER = "anthropic"
DEFAULT_LLM_MODEL = "claude-sonnet-4-20250514"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4096
DEFAULT_LLM_TIMEOUT = 60
DEFAULT_LLM_RETRIES = 3

# Default security settings
DEFAULT_SECURITY_MODE = "normal"
DEFAULT_MAX_COMMAND_LENGTH = 10000
DEFAULT_APPROVAL_TIMEOUT = 60

# Critical patterns that are ALWAYS blocked
CRITICAL_BLOCKED_PATTERNS = [
    r"^rm\s+-rf\s+/$",  # rm -rf /
    r"^rm\s+-rf\s+/\s*$",  # rm -rf / with trailing space
    r"^rm\s+-rf\s+/[^/]",  # rm -rf /something (root level)
    r"^mkfs\.",  # Format filesystem
    r"^dd\s+if=.*of=/dev",  # dd to device
    r":()\{\s*:\|:&\s*\};:",  # Fork bomb
    r">\s*/dev/sd[a-z]",  # Write directly to disk
    r"chmod\s+-R\s+777\s+/",  # Dangerous permission change at root
]

# High-risk patterns that require approval
HIGH_RISK_PATTERNS = [
    r"^rm\s+-rf\s+",  # Any recursive delete
    r"^sudo\s+",  # Privileged commands
    r"^(useradd|userdel|usermod)",  # User management
    r"^(groupadd|groupdel|groupmod)",  # Group management
    r"^systemctl\s+(stop|disable|mask)",  # Service management
    r"^(reboot|shutdown|poweroff|halt)",  # System control
    r"^chmod\s+-R",  # Recursive permission change
    r"^chown\s+-R",  # Recursive ownership change
]

# Medium-risk patterns
MEDIUM_RISK_PATTERNS = [
    r"^(apt|apt-get|yum|dnf)\s+(install|remove|purge)",  # Package management
    r"^pip\s+install",  # Python packages
    r"^npm\s+(install|uninstall)",  # Node packages
    r"^curl\s+.*\|\s*(bash|sh)",  # Pipe to shell
    r"^wget\s+.*\|\s*(bash|sh)",  # Pipe to shell
    r"^systemctl\s+(start|restart|reload)",  # Service control
    r">\s+/etc/",  # Write to /etc
]

# Default memory settings
DEFAULT_SESSION_MAX_ENTRIES = 100
DEFAULT_RETENTION_DAYS = {
    "configuration": 730,  # 2 years
    "incident": 365,  # 1 year
    "interaction": 90,  # 3 months
}

# Default telemetry settings
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_METRICS_PORT = 9090
DEFAULT_HEALTH_CHECK_INTERVAL = 60

# Default orchestrator settings
DEFAULT_SSH_TIMEOUT = 30
DEFAULT_MAX_PARALLEL_CONNECTIONS = 10
DEFAULT_MCP_PORT = 9999

# Tool execution defaults
DEFAULT_TOOL_TIMEOUT = 30
DEFAULT_TOOL_RETRIES = 2

# Agent execution defaults
DEFAULT_MAX_AGENT_STEPS = 10
DEFAULT_AGENT_TIMEOUT = 300  # 5 minutes for complex tasks


def ensure_default_dirs() -> None:
    """Ensure default directories exist."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DEFAULT_PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
