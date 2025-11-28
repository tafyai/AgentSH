# API Reference

This document describes the JSON schemas and tool contracts used by agentsh.

## AI Action Schema

The primary communication format between the LLM and agentsh.

### Complete Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "kind": {
      "type": "string",
      "enum": ["answer_only", "command_sequence", "plan_and_commands"],
      "description": "Type of response from AI"
    },
    "summary": {
      "type": "string",
      "description": "Brief explanation of what will be done"
    },
    "steps": {
      "type": "array",
      "items": {
        "$ref": "#/definitions/Step"
      },
      "description": "Ordered list of steps to execute"
    }
  },
  "required": ["kind"],
  "definitions": {
    "Step": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "description": "Unique identifier for this step"
        },
        "description": {
          "type": "string",
          "description": "Human-readable description of step purpose"
        },
        "shell_command": {
          "type": "string",
          "description": "The shell command to execute"
        },
        "needs_confirmation": {
          "type": "boolean",
          "default": false,
          "description": "Whether step requires explicit user confirmation"
        },
        "is_destructive": {
          "type": "boolean",
          "default": false,
          "description": "Whether step could cause data loss or damage"
        },
        "requires_sudo": {
          "type": "boolean",
          "default": false,
          "description": "Whether step requires elevated privileges"
        },
        "working_directory": {
          "type": "string",
          "description": "Directory to execute command in (optional)"
        }
      },
      "required": ["id", "description", "shell_command"]
    }
  }
}
```

### Action Kinds

| Kind | Description | When Used |
|------|-------------|-----------|
| `answer_only` | Text explanation, no commands | `ai explain`, informational queries |
| `command_sequence` | One or more commands to run | `ai run`, simple tasks |
| `plan_and_commands` | Multi-step plan with commands | `ai do`, complex tasks |

### Example Responses

#### answer_only

```json
{
  "kind": "answer_only",
  "summary": "The rsync command copies files from src/ to dst/ with archive mode, compression, and deletion of files not in source."
}
```

#### command_sequence

```json
{
  "kind": "command_sequence",
  "summary": "Find and terminate the process using port 8080",
  "steps": [
    {
      "id": "step1",
      "description": "Find the process using port 8080",
      "shell_command": "lsof -i :8080 -t"
    },
    {
      "id": "step2",
      "description": "Kill the process",
      "shell_command": "kill -9 $(lsof -i :8080 -t)",
      "needs_confirmation": true,
      "is_destructive": true
    }
  ]
}
```

#### plan_and_commands

```json
{
  "kind": "plan_and_commands",
  "summary": "Set up Dockerized PostgreSQL with persistent storage",
  "steps": [
    {
      "id": "step1",
      "description": "Check if Docker is installed",
      "shell_command": "docker --version"
    },
    {
      "id": "step2",
      "description": "Create directory for persistent data",
      "shell_command": "mkdir -p ~/postgres-data"
    },
    {
      "id": "step3",
      "description": "Create docker-compose.yml",
      "shell_command": "cat > docker-compose.yml << 'EOF'\nversion: '3.8'\nservices:\n  postgres:\n    image: postgres:15\n    volumes:\n      - ~/postgres-data:/var/lib/postgresql/data\n    environment:\n      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}\n    ports:\n      - \"5432:5432\"\nEOF"
    },
    {
      "id": "step4",
      "description": "Start PostgreSQL container",
      "shell_command": "docker-compose up -d",
      "needs_confirmation": true
    }
  ]
}
```

## System Prompt Contract

The LLM receives a system prompt defining its behavior.

### Core Instructions

```
You are a shell operations assistant for agentsh.

RULES:
1. You NEVER run commands directly - only propose actions in JSON
2. Prefer minimal, safe, auditable commands
3. Mark destructive operations (rm -rf, mkfs, dd, etc.) with is_destructive: true
4. Mark privileged operations with requires_sudo: true
5. Use available tools instead of guessing system state
6. For "ai explain" requests, respond with kind: "answer_only"

AVAILABLE TOOLS:
- sysinfo: Get OS, CPU, RAM, disk usage
- services: List running services
- packages: List installed packages
- fs.read_file: Read file contents (size-limited)

RESPONSE FORMAT:
Always respond with valid JSON matching the AiAction schema.
```

### Context Injection

The following context is appended to each request:

```json
{
  "context": {
    "os": "Linux 5.15.0-generic x86_64",
    "distro": "Ubuntu 22.04",
    "cwd": "/home/user/project",
    "user": "user",
    "last_command": "make deploy",
    "last_exit_code": 1,
    "last_stderr": "Error: missing dependency libfoo"
  }
}
```

## Plugin Tool API

External tools communicate via JSON over stdin/stdout.

### Request Format

```json
{
  "tool": "string",
  "action": "string",
  "args": {}
}
```

### Response Format

```json
{
  "ok": true,
  "stdout": "string",
  "stderr": "string",
  "meta": {
    "duration_ms": 0
  }
}
```

### Built-in Tools

#### cmd.run

Execute a shell command.

**Request:**
```json
{
  "tool": "cmd.run",
  "action": "execute",
  "args": {
    "command": "ls -la",
    "working_directory": "/tmp",
    "timeout_ms": 30000
  }
}
```

**Response:**
```json
{
  "ok": true,
  "stdout": "total 0\ndrwxrwxrwt  12 root root 240 Jan 15 10:00 .\n...",
  "stderr": "",
  "meta": {
    "duration_ms": 15,
    "exit_code": 0
  }
}
```

#### fs.read_file

Read file contents with size limits.

**Request:**
```json
{
  "tool": "fs.read_file",
  "action": "read",
  "args": {
    "path": "/etc/nginx/nginx.conf",
    "max_bytes": 10240
  }
}
```

**Response:**
```json
{
  "ok": true,
  "stdout": "worker_processes auto;\nevents {\n    worker_connections 1024;\n}\n...",
  "stderr": "",
  "meta": {
    "bytes_read": 1024,
    "truncated": false
  }
}
```

#### fs.write_file

Write file with backup.

**Request:**
```json
{
  "tool": "fs.write_file",
  "action": "write",
  "args": {
    "path": "/etc/nginx/sites-available/mysite",
    "content": "server {\n    listen 80;\n    ...\n}",
    "backup": true,
    "mode": "0644"
  }
}
```

**Response:**
```json
{
  "ok": true,
  "stdout": "",
  "stderr": "",
  "meta": {
    "backup_path": "/etc/nginx/sites-available/mysite.aishell-20240115100000.bak",
    "bytes_written": 256
  }
}
```

#### pkg.manage

Package manager abstraction.

**Request:**
```json
{
  "tool": "pkg.manage",
  "action": "install",
  "args": {
    "packages": ["nginx", "certbot"],
    "assume_yes": true
  }
}
```

**Response:**
```json
{
  "ok": true,
  "stdout": "Reading package lists...\nInstalling nginx...\n",
  "stderr": "",
  "meta": {
    "duration_ms": 15000,
    "packages_installed": ["nginx", "certbot"]
  }
}
```

**Actions:**
- `install` - Install packages
- `remove` - Remove packages
- `update` - Update package lists
- `upgrade` - Upgrade installed packages
- `search` - Search for packages

#### svc.manage

Service management abstraction.

**Request:**
```json
{
  "tool": "svc.manage",
  "action": "restart",
  "args": {
    "service": "nginx"
  }
}
```

**Response:**
```json
{
  "ok": true,
  "stdout": "",
  "stderr": "",
  "meta": {
    "duration_ms": 500,
    "service_state": "running"
  }
}
```

**Actions:**
- `start` - Start service
- `stop` - Stop service
- `restart` - Restart service
- `reload` - Reload service configuration
- `status` - Get service status
- `enable` - Enable service at boot
- `disable` - Disable service at boot

## Error Responses

### Tool Error

```json
{
  "ok": false,
  "stdout": "",
  "stderr": "Permission denied: /etc/shadow",
  "meta": {
    "error_code": "PERMISSION_DENIED"
  }
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `PERMISSION_DENIED` | Insufficient privileges |
| `NOT_FOUND` | File or resource not found |
| `TIMEOUT` | Operation timed out |
| `INVALID_ARGS` | Invalid arguments provided |
| `IO_ERROR` | I/O error occurred |
| `PARSE_ERROR` | Failed to parse input |

## WebSocket Events (Future)

For real-time streaming support:

### Command Output Stream

```json
{
  "event": "output",
  "step_id": "step1",
  "stream": "stdout",
  "data": "Installing package..."
}
```

### Step Completion

```json
{
  "event": "step_complete",
  "step_id": "step1",
  "exit_code": 0,
  "duration_ms": 1500
}
```

### Plan Complete

```json
{
  "event": "plan_complete",
  "success": true,
  "steps_executed": 4,
  "total_duration_ms": 5000
}
```
