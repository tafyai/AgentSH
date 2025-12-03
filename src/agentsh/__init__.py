"""
AgentSH - AI-enhanced terminal shell with LLM-powered capabilities.

AgentSH wraps traditional shells (Bash/Zsh/Fish) with intelligent features:
- Natural language to command translation
- Multi-step autonomous task execution
- Multi-device orchestration
- Strong security with human-in-the-loop
- Memory and context management
"""

__version__ = "0.1.0"
__author__ = "AgentSH Team"

from agentsh.config.schemas import AgentSHConfig

__all__ = [
    "__version__",
    "AgentSHConfig",
]
