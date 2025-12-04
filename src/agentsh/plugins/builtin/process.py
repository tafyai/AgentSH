"""Process toolset - Process management."""

import os
import signal
import subprocess
from typing import TYPE_CHECKING, Optional

from agentsh.plugins.base import Toolset
from agentsh.tools.base import RiskLevel, ToolResult

if TYPE_CHECKING:
    from agentsh.tools.registry import ToolRegistry


class ProcessToolset(Toolset):
    """Provides process management tools.

    Tools:
    - process.list: List running processes
    - process.info: Get process details
    - process.kill: Terminate a process
    """

    @property
    def name(self) -> str:
        return "process"

    @property
    def description(self) -> str:
        return "List, monitor, and manage system processes"

    def register_tools(self, registry: "ToolRegistry") -> None:
        """Register process tools."""
        registry.register_tool(
            name="process.list",
            handler=self.list_processes,
            description="List running processes with optional filtering by name.",
            parameters={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Filter processes by name (case-insensitive substring match)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of processes to return (default: 50)",
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["pid", "cpu", "mem", "name"],
                        "description": "Sort processes by field (default: cpu)",
                    },
                },
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="process.info",
            handler=self.get_process_info,
            description="Get detailed information about a specific process by PID.",
            parameters={
                "type": "object",
                "properties": {
                    "pid": {
                        "type": "integer",
                        "description": "Process ID",
                    },
                },
                "required": ["pid"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="process.kill",
            handler=self.kill_process,
            description="Terminate a process by sending a signal.",
            parameters={
                "type": "object",
                "properties": {
                    "pid": {
                        "type": "integer",
                        "description": "Process ID to kill",
                    },
                    "signal": {
                        "type": "string",
                        "enum": ["TERM", "KILL", "INT", "HUP"],
                        "description": "Signal to send (default: TERM)",
                    },
                },
                "required": ["pid"],
            },
            risk_level=RiskLevel.HIGH,
            requires_confirmation=True,
            plugin_name=self.name,
        )

    def list_processes(
        self,
        filter: Optional[str] = None,
        limit: int = 50,
        sort_by: str = "cpu",
    ) -> ToolResult:
        """List running processes.

        Args:
            filter: Filter by process name
            limit: Maximum results
            sort_by: Sort field (pid, cpu, mem, name)

        Returns:
            ToolResult with process list
        """
        try:
            # Use ps command for cross-platform compatibility
            # Format: PID, %CPU, %MEM, COMMAND
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"Failed to list processes: {result.stderr}",
                )

            lines = result.stdout.strip().split("\n")
            if not lines:
                return ToolResult(success=True, output="No processes found")

            # Parse header and data
            header = lines[0]
            processes = []

            for line in lines[1:]:
                parts = line.split(None, 10)
                if len(parts) < 11:
                    continue

                user, pid, cpu, mem, vsz, rss, tty, stat, start, time_str, cmd = (
                    parts[0],
                    parts[1],
                    parts[2],
                    parts[3],
                    parts[4],
                    parts[5],
                    parts[6],
                    parts[7],
                    parts[8],
                    parts[9],
                    parts[10] if len(parts) > 10 else "",
                )

                # Apply filter
                if filter and filter.lower() not in cmd.lower():
                    continue

                processes.append({
                    "pid": int(pid),
                    "user": user,
                    "cpu": float(cpu),
                    "mem": float(mem),
                    "command": cmd[:80],  # Truncate long commands
                })

            # Sort
            sort_key = {
                "pid": lambda x: x["pid"],
                "cpu": lambda x: -x["cpu"],
                "mem": lambda x: -x["mem"],
                "name": lambda x: x["command"].lower(),
            }.get(sort_by, lambda x: -x["cpu"])

            processes.sort(key=sort_key)
            processes = processes[:limit]

            if not processes:
                if filter:
                    return ToolResult(
                        success=True,
                        output=f"No processes matching '{filter}' found",
                    )
                return ToolResult(success=True, output="No processes found")

            # Format output
            output = ["PID      CPU%   MEM%   COMMAND"]
            output.append("-" * 60)
            for p in processes:
                output.append(
                    f"{p['pid']:<8} {p['cpu']:>5.1f}  {p['mem']:>5.1f}  {p['command']}"
                )

            return ToolResult(success=True, output="\n".join(output))

        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Command timed out")
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to list processes: {str(e)}",
            )

    def get_process_info(self, pid: int) -> ToolResult:
        """Get detailed process information.

        Args:
            pid: Process ID

        Returns:
            ToolResult with process details
        """
        try:
            # Check if process exists
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return ToolResult(
                    success=False,
                    error=f"Process {pid} not found",
                )
            except PermissionError:
                pass  # Process exists but we can't signal it

            # Get process info using ps
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "pid,ppid,user,%cpu,%mem,stat,start,time,command"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"Failed to get process info: {result.stderr}",
                )

            lines = result.stdout.strip().split("\n")
            if len(lines) < 2:
                return ToolResult(
                    success=False,
                    error=f"Process {pid} not found",
                )

            # Parse output
            header = lines[0]
            data = lines[1]

            # Try to get more info from /proc on Linux
            info = [f"Process: {pid}", "-" * 40]

            parts = data.split(None, 8)
            if len(parts) >= 9:
                info.append(f"Parent PID: {parts[1]}")
                info.append(f"User: {parts[2]}")
                info.append(f"CPU: {parts[3]}%")
                info.append(f"Memory: {parts[4]}%")
                info.append(f"Status: {parts[5]}")
                info.append(f"Started: {parts[6]}")
                info.append(f"CPU Time: {parts[7]}")
                info.append(f"Command: {parts[8]}")

            return ToolResult(success=True, output="\n".join(info))

        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Command timed out")
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get process info: {str(e)}",
            )

    def kill_process(
        self,
        pid: int,
        signal_name: str = "TERM",
    ) -> ToolResult:
        """Kill a process.

        Args:
            pid: Process ID
            signal_name: Signal to send (TERM, KILL, INT, HUP)

        Returns:
            ToolResult with success status
        """
        # Map signal names to signal numbers
        signal_map = {
            "TERM": signal.SIGTERM,
            "KILL": signal.SIGKILL,
            "INT": signal.SIGINT,
            "HUP": signal.SIGHUP,
        }

        sig = signal_map.get(signal_name.upper(), signal.SIGTERM)

        # Safety check - don't kill critical processes
        if pid <= 1:
            return ToolResult(
                success=False,
                error="Cannot kill process with PID <= 1",
            )

        # Don't kill our own process
        if pid == os.getpid():
            return ToolResult(
                success=False,
                error="Cannot kill the current process",
            )

        try:
            os.kill(pid, sig)
            return ToolResult(
                success=True,
                output=f"Sent {signal_name} signal to process {pid}",
            )

        except ProcessLookupError:
            return ToolResult(
                success=False,
                error=f"Process {pid} not found",
            )
        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied to kill process {pid}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to kill process: {str(e)}",
            )
