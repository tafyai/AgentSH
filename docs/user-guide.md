# User Guide

This guide covers everyday usage of agentsh, from basic commands to advanced workflows.

## Quick Start

### First Launch

After installation, start agentsh:

```bash
agentsh
```

You'll see a prompt like:

```
user@host:~/dir [ai:assist]$
```

The `[ai:assist]` indicator shows AI is available but not active.

### Your First AI Command

Try asking AI to help:

```bash
ai what is my current system info?
```

AI responds with system information, no commands executed.

### Running AI-Suggested Commands

```bash
ai find processes using more than 100MB of memory
```

AI proposes commands:

```
Plan:
  1. Find processes sorted by memory usage

Proposed commands:
  #1: ps aux --sort=-%mem | head -20

Run these? [y/e/n] y
```

- Press `y` to run
- Press `e` to edit the commands first
- Press `n` to cancel

## Command Reference

### Basic AI Commands

| Command | Description |
|---------|-------------|
| `ai <question>` | Ask a question or request help |
| `ai run "task"` | Get commands for a specific task |
| `ai explain 'command'` | Explain what a command does |
| `ai fix` | Diagnose and fix the last error |
| `ai do "task"` | Multi-step autonomous task |

### System Inspection

| Command | Description |
|---------|-------------|
| `ai sysinfo` | System overview (OS, CPU, RAM, disk) |
| `ai services` | List running services |
| `ai packages` | Show installed packages |

## Usage Examples

### Getting Help with Commands

**Finding files:**
```bash
ai find all log files larger than 100MB modified in the last week
```

**Network diagnostics:**
```bash
ai check what's listening on port 443 and show the process details
```

**Process management:**
```bash
ai show me the top CPU-consuming processes and help me identify any runaway processes
```

### Explaining Commands

```bash
ai explain 'find . -name "*.log" -mtime +7 -exec rm {} \;'
```

Output:
```
This command finds and deletes log files older than 7 days:

- `find .` - Search starting from current directory
- `-name "*.log"` - Match files ending in .log
- `-mtime +7` - Modified more than 7 days ago
- `-exec rm {} \;` - Execute rm on each match

⚠️ Warning: This permanently deletes files without confirmation.
```

### Fixing Errors

After a failed command:

```bash
$ make build
error: cannot find -lssl
$ ai fix
```

AI analyzes the error and suggests:

```
The error indicates missing SSL development libraries.

Plan:
  1. Install OpenSSL development package

Proposed commands:
  #1: sudo apt install libssl-dev

Run these? [y/e/n]
```

### Multi-Step Tasks

For complex tasks, use `ai do`:

```bash
ai do "set up a local development HTTPS server with a self-signed certificate"
```

AI creates a complete plan:

```
Plan:
  1. Check if OpenSSL is installed
  2. Generate a private key
  3. Create a self-signed certificate
  4. Create a simple Python HTTPS server script
  5. Start the server

Proposed commands:
  #1: openssl version
  #2: openssl genrsa -out localhost.key 2048
  #3: openssl req -new -x509 -key localhost.key -out localhost.crt -days 365 -subj "/CN=localhost"
  #4: cat > https_server.py << 'EOF'
      import http.server
      import ssl
      ...
      EOF
  #5: python3 https_server.py

Run these? [y/e/n]
```

## Working with Confirmations

### Confirmation Prompt

When AI proposes commands:

```
Run these? [y/e/n]
```

| Key | Action |
|-----|--------|
| `y` or `Enter` | Accept and run all commands |
| `e` | Edit commands before running |
| `n` | Cancel and return to prompt |

### Editing Commands

Press `e` to edit:

```
Edit step #1:
Current: rm -rf /tmp/old-files
New command (or Enter to keep, 'skip' to skip):
```

You can:
- Modify the command
- Press Enter to keep as-is
- Type `skip` to skip that step

### Destructive Command Warnings

Commands flagged as destructive show extra warnings:

```
⚠️  DESTRUCTIVE COMMAND
#2: rm -rf ~/old-project   [DESTRUCTIVE]

This will permanently delete files. Are you sure?
Type 'yes' to confirm:
```

### Sudo Commands

By default, sudo commands are shown but not auto-executed:

```
#3: sudo systemctl restart nginx   [SUDO]

sudo commands are not auto-executed.
Copy and run manually, or enable with:
  safety.allow_ai_to_execute_sudo = true
```

## Context and Project Integration

### Per-Project Configuration

Create `.aishellrc` in your project:

```toml
[context]
include_files = ["docker-compose.yml", "Makefile", "README.md"]
exclude_patterns = ["node_modules/*", "*.log"]
domain_hint = "nodejs-web-app"
```

AI now understands your project context.

### Domain Hints

Set `domain_hint` to help AI give better suggestions:

| Hint | AI Behavior |
|------|-------------|
| `nodejs-web-app` | Prioritizes npm, node commands |
| `python-ml` | Knows about pip, conda, jupyter |
| `kubernetes` | Uses kubectl, helm appropriately |
| `database-admin` | Focuses on SQL, backup strategies |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Alt-A` | Send current line to AI |
| `Alt-M` | Toggle AI mode (assist/off) |
| `Ctrl-C` | Cancel current AI operation |
| `Ctrl-D` | Exit shell |
| `↑/↓` | Navigate command history |
| `Tab` | Command/file completion |

## Modes

### Assist Mode (Default)

AI responds to explicit `ai` commands only.

```
user@host:~ [ai:assist]$
```

### Off Mode

AI is disabled; pure shell experience.

```bash
# Disable AI
ai mode off

# Or start with AI off
agentsh --mode off
```

Prompt changes to:
```
user@host:~ [shell]$
```

### Switching Modes

```bash
ai mode assist   # Enable AI assist
ai mode off      # Disable AI
```

Or use `Alt-M` to toggle.

## Logging and History

### View AI Command History

```bash
cat ~/.aishell/logs/commands.log
```

Or use:
```bash
ai history
```

### Disable Logging

```toml
[safety]
log_ai_generated_commands = false
```

## Customization

### Custom Prompt

In `~/.aishell/config.toml`:

```toml
[ui]
prompt = "{user}@{host}:{cwd} ({mode})$ "
```

Variables:
- `{user}` - Username
- `{host}` - Hostname
- `{cwd}` - Current directory
- `{mode}` - AI mode indicator

### Color Scheme

```toml
[ui.colors]
prompt_user = "green"
prompt_host = "blue"
ai_command = "yellow"
ai_warning = "red"
```

### Different Shell

```toml
[mode]
shell = "/bin/zsh"
shell_args = ["-l"]
```

Or via command line:
```bash
agentsh /bin/zsh
```

## Tips and Best Practices

### Be Specific

❌ Less effective:
```bash
ai fix my server
```

✅ More effective:
```bash
ai nginx returns 502 bad gateway, check the upstream connection to my nodejs app on port 3000
```

### Review Before Running

Always review the proposed commands, especially:
- Commands with `[DESTRUCTIVE]` flag
- Commands with `[SUDO]` flag
- Commands that modify system configuration

### Use Explain First

When unsure about a command:

```bash
ai explain 'the-command-you-found-online'
```

### Leverage Context

Set up `.aishellrc` for your projects to get context-aware suggestions.

### Keep Logs

Enable logging for:
- Auditing what commands were run
- Learning from past AI suggestions
- Troubleshooting issues

## Troubleshooting

### AI Not Responding

1. Check internet connection
2. Verify API key is set: `echo $OPENAI_API_KEY`
3. Check config: `cat ~/.aishell/config.toml`
4. Try with debug: `agentsh --debug`

### Commands Not Executing

Check if commands are blocked:
```toml
[safety]
blocked_patterns = [...]  # Check this list
```

Or if sudo is disabled:
```toml
[safety]
allow_ai_to_execute_sudo = false
```

### Shell Feels Slow

1. Check network latency to AI endpoint
2. Consider using a faster model
3. Reduce context size:
   ```toml
   [context]
   max_context_size = 262144  # Reduce from default
   ```

### Exiting agentsh

Standard exit commands work:
```bash
exit
logout
# Or Ctrl-D
```

If stuck, use:
```bash
# Ctrl-C to cancel current operation
# Ctrl-D to exit
```

## Getting Help

```bash
ai help           # AI-powered help
agentsh --help    # CLI help
ai explain 'ai'   # Meta-help about AI commands
```

For issues, visit: https://github.com/yourusername/agentsh/issues
