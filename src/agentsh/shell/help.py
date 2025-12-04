"""Help system for AgentSH.

Provides topic-based help with detailed documentation
for all commands, features, and usage patterns.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from agentsh.utils.ux import Color, OutputBuffer, colorize


class HelpCategory(str, Enum):
    """Categories for help topics."""

    GETTING_STARTED = "getting_started"
    COMMANDS = "commands"
    AI = "ai"
    SHELL = "shell"
    SECURITY = "security"
    TOOLS = "tools"
    CONFIGURATION = "configuration"
    TROUBLESHOOTING = "troubleshooting"


@dataclass
class HelpTopic:
    """A help topic with documentation.

    Attributes:
        name: Topic name (used for :help <topic>)
        title: Display title
        category: Topic category
        summary: One-line summary
        content: Full documentation
        aliases: Alternative names for the topic
        see_also: Related topics
    """

    name: str
    title: str
    category: HelpCategory
    summary: str
    content: str
    aliases: list[str] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)


class HelpSystem:
    """Help system with topic-based documentation.

    Provides:
    - Topic lookup by name or alias
    - Category-based browsing
    - Search functionality
    - Formatted output

    Example:
        help_system = HelpSystem()
        help_system.show("commands")  # Show commands topic
        help_system.list_topics()  # List all topics
        help_system.search("ai")  # Search for AI-related help
    """

    def __init__(self) -> None:
        """Initialize help system with built-in topics."""
        self._topics: dict[str, HelpTopic] = {}
        self._aliases: dict[str, str] = {}
        self._register_builtin_topics()

    def register(self, topic: HelpTopic) -> None:
        """Register a help topic.

        Args:
            topic: Help topic to register
        """
        self._topics[topic.name] = topic
        for alias in topic.aliases:
            self._aliases[alias] = topic.name

    def get(self, name: str) -> Optional[HelpTopic]:
        """Get a help topic by name or alias.

        Args:
            name: Topic name or alias

        Returns:
            HelpTopic or None if not found
        """
        name_lower = name.lower()

        # Try direct lookup
        if name_lower in self._topics:
            return self._topics[name_lower]

        # Try alias lookup
        if name_lower in self._aliases:
            return self._topics[self._aliases[name_lower]]

        return None

    def list_topics(self, category: Optional[HelpCategory] = None) -> list[HelpTopic]:
        """List all topics, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of topics
        """
        topics = list(self._topics.values())
        if category:
            topics = [t for t in topics if t.category == category]
        return sorted(topics, key=lambda t: (t.category.value, t.name))

    def search(self, query: str) -> list[HelpTopic]:
        """Search for topics matching query.

        Args:
            query: Search query

        Returns:
            List of matching topics
        """
        query_lower = query.lower()
        results = []

        for topic in self._topics.values():
            # Search in name, title, summary, and content
            if (
                query_lower in topic.name.lower()
                or query_lower in topic.title.lower()
                or query_lower in topic.summary.lower()
                or query_lower in topic.content.lower()
            ):
                results.append(topic)

        return sorted(results, key=lambda t: t.name)

    def format_topic(self, topic: HelpTopic, use_color: bool = True) -> str:
        """Format a help topic for display.

        Args:
            topic: Topic to format
            use_color: Whether to use colors

        Returns:
            Formatted string
        """
        buf = OutputBuffer(use_color=use_color)

        # Title
        buf.add_header(topic.title, level=1)
        buf.add_line("")

        # Summary
        if use_color:
            buf.add_line(colorize(topic.summary, Color.DIM))
        else:
            buf.add_line(topic.summary)
        buf.add_line("")

        # Content
        buf.add(topic.content)
        buf.add_line("")

        # See also
        if topic.see_also:
            buf.add_separator()
            buf.add_line("See also:")
            for ref in topic.see_also:
                buf.add_line(f"  :help {ref}")

        return buf.render()

    def format_overview(self, use_color: bool = True) -> str:
        """Format the help overview.

        Args:
            use_color: Whether to use colors

        Returns:
            Formatted overview string
        """
        buf = OutputBuffer(use_color=use_color)

        buf.add_header("AgentSH Help", level=1)
        buf.add_line("")
        buf.add_line("Type :help <topic> for detailed help on a topic.")
        buf.add_line("Type :help all to list all topics.")
        buf.add_line("")

        # Group by category
        for category in HelpCategory:
            topics = self.list_topics(category)
            if not topics:
                continue

            buf.add_header(category.value.replace("_", " ").title(), level=2)
            for topic in topics:
                name = f"  {topic.name:<20}"
                if use_color:
                    buf.add_line(f"{colorize(name, Color.CYAN)}{topic.summary}")
                else:
                    buf.add_line(f"{name}{topic.summary}")
            buf.add_line("")

        return buf.render()

    def format_topic_list(self, use_color: bool = True) -> str:
        """Format a list of all topics.

        Args:
            use_color: Whether to use colors

        Returns:
            Formatted topic list
        """
        buf = OutputBuffer(use_color=use_color)

        buf.add_header("All Help Topics", level=1)
        buf.add_line("")

        current_category = None
        for topic in self.list_topics():
            if topic.category != current_category:
                current_category = topic.category
                buf.add_header(current_category.value.replace("_", " ").title(), level=2)

            name = f"  {topic.name:<20}"
            aliases = f" (aliases: {', '.join(topic.aliases)})" if topic.aliases else ""
            if use_color:
                buf.add_line(f"{colorize(name, Color.CYAN)}{topic.summary}{colorize(aliases, Color.DIM)}")
            else:
                buf.add_line(f"{name}{topic.summary}{aliases}")

        buf.add_line("")
        return buf.render()

    def show(self, topic_name: Optional[str] = None, use_color: bool = True) -> str:
        """Show help for a topic or overview.

        Args:
            topic_name: Topic name (None for overview)
            use_color: Whether to use colors

        Returns:
            Formatted help string
        """
        if not topic_name:
            return self.format_overview(use_color)

        if topic_name.lower() == "all":
            return self.format_topic_list(use_color)

        topic = self.get(topic_name)
        if topic:
            return self.format_topic(topic, use_color)

        # Not found - suggest similar topics
        similar = self.search(topic_name)
        if similar:
            buf = OutputBuffer(use_color=use_color)
            buf.add_line(f"No help topic found for '{topic_name}'.")
            buf.add_line("")
            buf.add_line("Did you mean:")
            for t in similar[:5]:
                buf.add_line(f"  :help {t.name}")
            return buf.render()

        return f"No help topic found for '{topic_name}'. Type :help for available topics."

    def _register_builtin_topics(self) -> None:
        """Register all built-in help topics."""
        # Getting Started
        self.register(
            HelpTopic(
                name="intro",
                title="Introduction to AgentSH",
                category=HelpCategory.GETTING_STARTED,
                summary="Overview of AgentSH and its capabilities",
                aliases=["introduction", "overview", "about"],
                content="""
AgentSH is an AI-enhanced terminal shell that combines traditional shell
functionality with AI-powered assistance.

Key Features:
  - Natural language commands processed by AI
  - Traditional shell commands work normally
  - Tool execution with safety controls
  - Multi-device orchestration
  - Session history and memory

Quick Start:
  1. Type shell commands normally (ls, cd, git, etc.)
  2. Use natural language for complex tasks
  3. Use :help commands to see all available commands
  4. Use :status to check system status
""",
                see_also=["commands", "ai", "shell"],
            )
        )

        self.register(
            HelpTopic(
                name="quickstart",
                title="Quick Start Guide",
                category=HelpCategory.GETTING_STARTED,
                summary="Get started with AgentSH in 5 minutes",
                aliases=["start", "tutorial"],
                content="""
Quick Start Guide
=================

1. BASIC SHELL USAGE
   Regular shell commands work as expected:
   $ ls -la
   $ cd /path/to/project
   $ git status

2. AI ASSISTANCE
   Ask the AI for help with natural language:
   $ find all Python files modified today
   $ explain what this error means
   $ write a function to sort a list

3. FORCE MODES
   Force shell execution with '!' prefix:
   $ !ls -la

   Force AI mode with 'ai ' prefix:
   $ ai explain this code

4. SPECIAL COMMANDS
   Use colon commands for AgentSH features:
   :help     - Show help
   :status   - Show system status
   :history  - Show command history
   :config   - Show configuration

5. GETTING HELP
   :help <topic>  - Help on specific topic
   :help commands - List all commands
   :help ai       - AI usage guide
""",
                see_also=["intro", "commands", "ai"],
            )
        )

        # Commands
        self.register(
            HelpTopic(
                name="commands",
                title="Special Commands",
                category=HelpCategory.COMMANDS,
                summary="List of all special commands",
                aliases=["cmds", "cmd"],
                content="""
Special Commands (prefix with ':')
==================================

Navigation & Display:
  :help [topic]    Show help (optionally for a topic)
  :clear           Clear the screen
  :status          Show system status

Session Management:
  :history [n]     Show command history (last n entries)
  :reset           Reset AI conversation context
  :config          Show current configuration

Exit:
  :quit            Exit AgentSH
  :exit            Exit AgentSH (alias)
  :q               Exit AgentSH (short alias)

Input Prefixes:
  !<command>       Force shell execution
  ai <request>     Force AI processing
""",
                see_also=["history", "config", "status"],
            )
        )

        self.register(
            HelpTopic(
                name="history",
                title="Command History",
                category=HelpCategory.COMMANDS,
                summary="Using command history",
                content="""
Command History
===============

View History:
  :history         Show recent commands (default: 20)
  :history 50      Show last 50 commands
  :history --ai    Show only AI requests
  :history --shell Show only shell commands

Navigation:
  Up/Down arrows   Navigate through history
  Ctrl+R           Search history (reverse)

History is automatically saved between sessions.

Notes:
  - History is stored in ~/.agentsh/history
  - Maximum entries configured in settings
  - AI requests and shell commands tracked separately
""",
                see_also=["commands", "config"],
            )
        )

        self.register(
            HelpTopic(
                name="status",
                title="System Status",
                category=HelpCategory.COMMANDS,
                summary="Check system health and status",
                content="""
System Status
=============

The :status command shows:
  - Component health (LLM, tools, memory)
  - Connection status to external services
  - Resource usage
  - Session information

Health Indicators:
  [OK]     Component is working normally
  [WARN]   Component has warnings
  [ERROR]  Component has errors
  [N/A]    Component not configured

Use :status to diagnose issues with:
  - LLM connectivity
  - Tool availability
  - Memory system
  - Security configuration
""",
                see_also=["config", "troubleshooting"],
            )
        )

        # AI
        self.register(
            HelpTopic(
                name="ai",
                title="AI Usage Guide",
                category=HelpCategory.AI,
                summary="How to use AI features effectively",
                aliases=["llm", "assistant"],
                content="""
AI Usage Guide
==============

Natural Language Input:
  The AI understands natural language requests:
  $ find all log files from today
  $ explain what this error message means
  $ help me write a Python function for sorting

Forcing AI Mode:
  Use the 'ai ' prefix to ensure AI processing:
  $ ai ls -la  (AI will explain the command)

Best Practices:
  1. Be specific about what you want
  2. Provide context when needed
  3. Use :reset to clear conversation context
  4. Review AI-suggested commands before executing

Tool Usage:
  The AI can use tools to:
  - Execute shell commands
  - Read and write files
  - Search code
  - Manage processes

Safety:
  - High-risk commands require confirmation
  - Some operations are blocked by policy
  - Use :config to see security settings
""",
                see_also=["tools", "security", "prompts"],
            )
        )

        self.register(
            HelpTopic(
                name="prompts",
                title="Effective Prompts",
                category=HelpCategory.AI,
                summary="Tips for writing effective AI prompts",
                content="""
Writing Effective Prompts
=========================

Good Prompts:
  - "Find all Python files larger than 1MB in src/"
  - "Explain what the error 'Connection refused' means"
  - "Create a bash script to backup my home directory"

Less Effective:
  - "help" (too vague)
  - "do something with files" (unclear goal)
  - "fix it" (missing context)

Tips:
  1. State the goal clearly
  2. Include relevant context
  3. Specify constraints or requirements
  4. Use examples when helpful

Context:
  The AI remembers conversation context. Use :reset
  to start fresh if the context becomes confusing.
""",
                see_also=["ai", "tools"],
            )
        )

        # Shell
        self.register(
            HelpTopic(
                name="shell",
                title="Shell Integration",
                category=HelpCategory.SHELL,
                summary="How shell integration works",
                content="""
Shell Integration
=================

AgentSH wraps your default shell and adds AI capabilities.

Shell Commands:
  Regular commands work normally:
  $ ls -la
  $ git status
  $ docker ps

Force Shell Mode:
  Use '!' prefix to ensure shell execution:
  $ !find . -name "*.py"

Classification:
  AgentSH automatically classifies input as either:
  - Shell command (executed directly)
  - AI request (processed by AI)

The classifier uses patterns and heuristics. When
uncertain, it defaults to shell execution (configurable).

Environment:
  - Shell: $SHELL or /bin/bash
  - Working directory preserved
  - Environment variables inherited
""",
                see_also=["commands", "config"],
            )
        )

        # Security
        self.register(
            HelpTopic(
                name="security",
                title="Security Model",
                category=HelpCategory.SECURITY,
                summary="Understanding security controls",
                content="""
Security Model
==============

AgentSH implements multiple security layers:

1. Risk Classification:
   - LOW: Safe operations (reading files, listing)
   - MEDIUM: System modifications (file changes)
   - HIGH: Privileged operations (sudo, system config)
   - CRITICAL: Potentially dangerous (rm -rf, etc.)

2. Approval Flow:
   - Low risk: Auto-approved
   - Medium risk: Configurable
   - High/Critical: Requires confirmation

3. Command Blocking:
   Certain commands are blocked by default:
   - rm -rf /
   - Format commands
   - Fork bombs

4. RBAC (Role-Based Access Control):
   Roles determine what actions are permitted.

5. Audit Logging:
   All commands are logged for audit purposes.

See :config for current security settings.
""",
                see_also=["config", "tools"],
            )
        )

        # Tools
        self.register(
            HelpTopic(
                name="tools",
                title="Available Tools",
                category=HelpCategory.TOOLS,
                summary="Tools the AI can use",
                content="""
Available Tools
===============

Shell Tools:
  execute_command  - Run shell commands
  read_file        - Read file contents
  write_file       - Write to files
  list_directory   - List directory contents

Code Tools:
  search_code      - Search for code patterns
  analyze_code     - Analyze code structure
  format_code      - Format source code

Process Tools:
  list_processes   - List running processes
  kill_process     - Terminate a process

Remote Tools (Multi-device):
  remote_execute   - Run command on remote device
  remote_copy      - Copy files to/from remote

Tool Execution:
  - Tools are called by the AI to fulfill requests
  - Each tool has specific parameters
  - Results are returned to the AI for processing
""",
                see_also=["ai", "security"],
            )
        )

        # Configuration
        self.register(
            HelpTopic(
                name="config",
                title="Configuration",
                category=HelpCategory.CONFIGURATION,
                summary="Configuring AgentSH",
                aliases=["configuration", "settings"],
                content="""
Configuration
=============

Configuration File:
  ~/.agentsh/config.yaml

Key Settings:
  shell:
    backend: /bin/bash      # Shell to use
    ai_prefix: "ai "        # Prefix for AI mode
    shell_prefix: "!"       # Prefix for shell mode

  llm:
    provider: anthropic     # LLM provider
    model: claude-sonnet-4-20250514  # Model name
    api_key: $ANTHROPIC_API_KEY

  security:
    mode: balanced          # strict, balanced, permissive
    require_approval: true  # For high-risk commands

View Current Config:
  :config

Environment Variables:
  AGENTSH_CONFIG     - Config file path
  ANTHROPIC_API_KEY  - Anthropic API key
  OPENAI_API_KEY     - OpenAI API key
""",
                see_also=["security", "shell"],
            )
        )

        # Troubleshooting
        self.register(
            HelpTopic(
                name="troubleshooting",
                title="Troubleshooting",
                category=HelpCategory.TROUBLESHOOTING,
                summary="Common issues and solutions",
                aliases=["debug", "problems", "issues"],
                content="""
Troubleshooting
===============

AI Not Responding:
  1. Check :status for LLM connectivity
  2. Verify API key is set correctly
  3. Check network connectivity
  4. Try :reset to clear context

Commands Not Executing:
  1. Use '!' prefix to force shell mode
  2. Check security settings with :config
  3. Verify command is not blocked

History Not Saving:
  1. Check ~/.agentsh/ directory exists
  2. Verify write permissions
  3. Check disk space

Performance Issues:
  1. Use :reset to clear long context
  2. Check memory usage in :status
  3. Consider using local LLM

Getting More Help:
  - :help <topic> for specific help
  - Check logs in ~/.agentsh/logs/
  - Report issues on GitHub
""",
                see_also=["status", "config"],
            )
        )

        self.register(
            HelpTopic(
                name="errors",
                title="Common Errors",
                category=HelpCategory.TROUBLESHOOTING,
                summary="Common error messages and fixes",
                content="""
Common Errors
=============

"API key not configured"
  Solution: Set ANTHROPIC_API_KEY or OPENAI_API_KEY
  environment variable.

"Connection refused"
  Solution: Check network connectivity and firewall
  settings. Verify the LLM service is accessible.

"Rate limit exceeded"
  Solution: Wait and retry. Consider using a different
  provider or upgrading your API plan.

"Command blocked by policy"
  Solution: The command is blocked for safety. If you
  need to run it, use the shell directly.

"Permission denied"
  Solution: Check file permissions. You may need sudo
  for certain operations.

"Context too long"
  Solution: Use :reset to clear conversation context.
  The conversation history may be too large.
""",
                see_also=["troubleshooting", "status"],
            )
        )


# Global help system instance
_help_system: Optional[HelpSystem] = None


def get_help_system() -> HelpSystem:
    """Get the global help system instance.

    Returns:
        HelpSystem instance
    """
    global _help_system
    if _help_system is None:
        _help_system = HelpSystem()
    return _help_system


def show_help(topic: Optional[str] = None, use_color: bool = True) -> str:
    """Convenience function to show help.

    Args:
        topic: Topic name or None for overview
        use_color: Whether to use colors

    Returns:
        Formatted help string
    """
    return get_help_system().show(topic, use_color)
