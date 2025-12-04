"""
AgentSH CLI entry point.

Usage:
    agentsh                     Start interactive shell
    agentsh --version           Show version
    agentsh --config <path>     Use custom config file
    agentsh config show         Show current configuration
    agentsh status              Check system health
    agentsh --mcp-server        Run as MCP server (for remote LLM integration)
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

from agentsh import __version__
from agentsh.config.loader import load_config
from agentsh.telemetry.logger import setup_logging, get_logger


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="agentsh",
        description="AI-enhanced terminal shell with LLM-powered capabilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agentsh                    Start interactive shell
  agentsh --config ~/my.yaml Use custom configuration
  agentsh config show        Display current settings
  agentsh status             Check health of all components

For more information, visit: https://github.com/agentsh/agentsh
        """,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    parser.add_argument(
        "--config",
        type=Path,
        metavar="PATH",
        help="Path to custom configuration file",
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default=None,
        help="Override log level",
    )

    parser.add_argument(
        "--mcp-server",
        action="store_true",
        help="Run as MCP server for remote LLM integration",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # config subcommand
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    config_subparsers.add_parser("show", help="Show current configuration")
    config_subparsers.add_parser("init", help="Initialize default configuration")

    # status subcommand
    subparsers.add_parser("status", help="Check system health")

    # devices subcommand (placeholder for Phase 8)
    devices_parser = subparsers.add_parser("devices", help="Device management")
    devices_subparsers = devices_parser.add_subparsers(dest="devices_command")
    devices_subparsers.add_parser("list", help="List all devices")
    devices_add = devices_subparsers.add_parser("add", help="Add a device")
    devices_add.add_argument("host", help="Device hostname or IP")
    devices_remove = devices_subparsers.add_parser("remove", help="Remove a device")
    devices_remove.add_argument("device_id", help="Device ID to remove")

    return parser


def cmd_config_show(config_path: Optional[Path]) -> int:
    """Show current configuration."""
    try:
        config = load_config(config_path)
        print("Current AgentSH Configuration:")
        print("=" * 50)
        print(config.model_dump_json(indent=2))
        return 0
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1


def cmd_config_init(config_path: Optional[Path]) -> int:
    """Initialize default configuration file."""
    from agentsh.config.loader import get_default_config_path, create_default_config

    target_path = config_path or get_default_config_path()
    try:
        create_default_config(target_path)
        print(f"Created default configuration at: {target_path}")
        return 0
    except Exception as e:
        print(f"Error creating configuration: {e}", file=sys.stderr)
        return 1


def cmd_status() -> int:
    """Check system health."""
    from agentsh.telemetry.health import HealthChecker

    print("AgentSH System Status")
    print("=" * 50)

    checker = HealthChecker()
    status = checker.check_all()

    for component, result in status.items():
        icon = "✓" if result.healthy else "✗"
        print(f"{icon} {component}: {result.status}")
        if result.message:
            print(f"  └─ {result.message}")

    overall = all(r.healthy for r in status.values())
    print()
    print(f"Overall: {'Healthy' if overall else 'Unhealthy'}")
    return 0 if overall else 1


def cmd_mcp_server(config_path: Optional[Path]) -> int:
    """Run as MCP server."""
    print("MCP Server mode - Coming in Phase 8")
    print("This will expose AgentSH tools via the Model Context Protocol.")
    return 0


def cmd_devices(args: argparse.Namespace) -> int:
    """Device management commands."""
    print("Device management - Coming in Phase 8")
    return 0


def cmd_interactive_shell(config_path: Optional[Path], log_level: Optional[str]) -> int:
    """Start the interactive shell."""
    from agentsh.shell.wrapper import ShellWrapper

    try:
        config = load_config(config_path)

        if log_level:
            config.log_level = log_level

        setup_logging(config.log_level, config.telemetry.log_file)
        logger = get_logger(__name__)
        logger.info("Starting AgentSH", version=__version__)

        shell = ShellWrapper(config)

        # Set up AI handler if API key is configured
        if config.llm.api_key:
            try:
                from agentsh.agent.factory import create_ai_handler

                ai_handler = create_ai_handler(config)
                shell.set_ai_handler(ai_handler)
                logger.info(
                    "AI handler configured",
                    provider=config.llm.provider.value,
                    model=config.llm.model,
                )
            except Exception as e:
                logger.warning("Failed to configure AI handler", error=str(e))
                # Continue without AI - will show placeholder

        shell.run()
        return 0

    except KeyboardInterrupt:
        print("\nGoodbye!")
        return 0
    except Exception as e:
        print(f"Error starting AgentSH: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Handle subcommands
    if args.command == "config":
        if args.config_command == "show":
            return cmd_config_show(args.config)
        elif args.config_command == "init":
            return cmd_config_init(args.config)
        else:
            parser.parse_args(["config", "--help"])
            return 1

    elif args.command == "status":
        return cmd_status()

    elif args.command == "devices":
        return cmd_devices(args)

    elif args.mcp_server:
        return cmd_mcp_server(args.config)

    else:
        # Default: start interactive shell
        return cmd_interactive_shell(args.config, args.log_level)


if __name__ == "__main__":
    sys.exit(main())
