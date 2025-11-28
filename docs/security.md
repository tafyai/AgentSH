# Security Model

This document describes agentsh's security architecture, threat model, and safety mechanisms.

## Security Principles

agentsh follows three core security principles:

1. **Least Surprise** - AI never runs commands without user awareness
2. **Least Privilege** - AI never bypasses normal authentication
3. **Auditability** - All AI-generated commands are visible and loggable

## Threat Model

### In Scope

| Threat | Mitigation |
|--------|------------|
| Accidental destructive commands | Destructive command detection + confirmation |
| Unauthorized privilege escalation | sudo command flagging + execution controls |
| Data exfiltration via AI | Local-only context, no automatic uploads |
| Command injection in AI responses | JSON schema validation + command parsing |
| Credential exposure in logs | Secret redaction + configurable logging |

### Out of Scope

- Compromise of the underlying OS/shell
- Malicious LLM provider responses
- Physical access attacks
- Network-level attacks on SSH

## Destructive Command Detection

The safety module analyzes proposed commands for dangerous patterns.

### Detection Categories

#### Filesystem Operations

```
rm -rf                  # Recursive forced deletion
rm -r /                 # Root deletion
mv / ...                # Moving root
chmod -R 777 /          # Recursive permission changes
chown -R ...            # Recursive ownership changes
```

#### Block Device Operations

```
dd if=... of=/dev/sd*   # Writing to block devices
mkfs.*                  # Formatting filesystems
fdisk /dev/*            # Partition manipulation
parted /dev/*           # Partition manipulation
wipefs                  # Filesystem signature wiping
```

#### Network/Firewall

```
iptables -F             # Flushing firewall rules
iptables -P ... DROP    # Changing default policies
ufw disable             # Disabling firewall
firewall-cmd --panic-on # Panic mode
```

#### System Services

```
systemctl stop sshd     # Stopping SSH (lockout risk)
systemctl disable *     # Disabling services
service * stop          # Legacy service control
kill -9 1               # Killing init
```

#### Package Management

```
apt remove *            # Package removal
yum remove *            # Package removal
dnf remove *            # Package removal
pacman -R *             # Package removal
pip uninstall *         # Python package removal
npm uninstall *         # Node package removal
```

### Detection Implementation

```rust
fn analyze_command(cmd: &str) -> SafetyFlags {
    let mut flags = SafetyFlags::default();

    // Check for destructive patterns
    if DESTRUCTIVE_PATTERNS.iter().any(|p| p.is_match(cmd)) {
        flags.is_destructive = true;
    }

    // Check for sudo
    if cmd.starts_with("sudo ") || cmd.contains("| sudo ") {
        flags.requires_sudo = true;
    }

    // Check for critical services
    if CRITICAL_SERVICES.iter().any(|s| cmd.contains(s)) {
        flags.affects_critical_service = true;
    }

    flags
}
```

## Execution Controls

### Confirmation Levels

| Flag | Default Behavior |
|------|------------------|
| `is_destructive` | Requires explicit "yes" confirmation |
| `requires_sudo` | Requires confirmation + respects `allow_ai_to_execute_sudo` |
| `affects_critical_service` | Shows warning + requires confirmation |

### Sudo Handling

```toml
[safety]
allow_ai_to_execute_sudo = false  # Default
```

When `allow_ai_to_execute_sudo = false`:
- agentsh displays sudo commands but does NOT execute them
- User must copy/paste or run manually
- Prevents accidental privilege escalation

When `allow_ai_to_execute_sudo = true`:
- agentsh executes sudo commands after confirmation
- User's sudo session/credentials are used normally
- agentsh never stores or handles sudo passwords

### Blocked Commands

Some commands are never executed automatically:

```toml
[safety]
blocked_patterns = [
    "rm -rf /",
    "rm -rf /*",
    "> /dev/sd[a-z]",
    "mkfs.* /dev/sd[a-z]$",
    "dd.*of=/dev/sd[a-z]$",
    ":(){:|:&};:",  # Fork bomb
]
```

Blocked commands show an error and require manual execution.

## Input Validation

### AI Response Validation

All AI responses are validated against the JSON schema:

1. **Structure validation** - Must match `AiAction` schema
2. **Field validation** - Required fields present, correct types
3. **Command sanitization** - No control characters, reasonable length

Invalid responses fall back to `AnswerOnly` mode (text display only).

### Command Parsing

Before execution, commands are parsed to:
- Detect shell metacharacters
- Identify potential injection attempts
- Validate path arguments

```rust
fn validate_command(cmd: &str) -> Result<(), ValidationError> {
    // Check for suspicious patterns
    if cmd.contains("$(") && cmd.contains("curl") {
        return Err(ValidationError::SuspiciousPattern);
    }

    // Check command length
    if cmd.len() > MAX_COMMAND_LENGTH {
        return Err(ValidationError::TooLong);
    }

    Ok(())
}
```

## Context Security

### Data Sent to AI

The following context is sent to the LLM:

| Data | Purpose | Privacy Note |
|------|---------|--------------|
| OS/distro | Platform-specific commands | Low sensitivity |
| Working directory | Path context | May reveal project structure |
| Recent commands | Error fixing | Filtered for secrets |
| File contents | Project context | Size-limited, pattern-filtered |

### Data NOT Sent

- SSH keys or credentials
- Environment variables with secrets
- Files matching exclude patterns
- Full command history

### Secret Filtering

Commands and output are filtered before sending to AI:

```rust
fn filter_secrets(text: &str) -> String {
    let patterns = [
        r"[A-Za-z0-9_-]{20,}",          // API keys
        r"(?i)password\s*[=:]\s*\S+",    // Passwords
        r"-----BEGIN.*PRIVATE KEY-----", // Private keys
        r"Bearer\s+[A-Za-z0-9._-]+",     // Bearer tokens
    ];

    let mut filtered = text.to_string();
    for pattern in patterns {
        filtered = regex.replace_all(&filtered, "[REDACTED]");
    }
    filtered
}
```

## Audit Logging

### Log Format

```json
{
  "session_id": "abc123-def456",
  "timestamp": "2024-01-15T10:30:00Z",
  "event": "command_executed",
  "user": "alice",
  "request": "find and kill port 8080",
  "ai_response": {
    "kind": "command_sequence",
    "steps": [...]
  },
  "executed_commands": [
    {"command": "lsof -i :8080", "exit_code": 0},
    {"command": "kill 12345", "exit_code": 0}
  ],
  "duration_ms": 1500
}
```

### Log Security

- Logs are written with restrictive permissions (0600)
- Log directory has restricted access (0700)
- Secrets are redacted before logging
- Log rotation prevents unbounded growth

### Configuration

```toml
[safety]
log_ai_generated_commands = true
log_path = "~/.aishell/logs/commands.log"
max_log_size = 10485760  # 10MB
log_retention = 5        # Keep 5 rotated logs
redact_secrets = true
```

## Network Security

### LLM Communication

- All API calls use HTTPS
- TLS certificate validation enabled
- API keys read from environment variables (never stored in config)
- Request timeout prevents hanging
- No sensitive data in query parameters

### Configuration

```toml
[ai]
endpoint = "https://api.openai.com/v1/chat/completions"
api_key_env = "OPENAI_API_KEY"  # Read from env, not stored
timeout = 30
```

## Graceful Degradation

If the AI backend is unreachable:

1. Shell continues to function normally
2. `ai` commands show clear error message
3. No data is queued for later transmission
4. User can continue work uninterrupted

```
$ ai find files
Error: AI backend unreachable (connection timed out)
Shell continues normally. Use standard commands or try again later.
```

## Security Best Practices

### For Users

1. **Review AI plans before execution** - Don't blindly accept
2. **Keep `allow_ai_to_execute_sudo = false`** - Default is safest
3. **Use per-project configs** - Limit context to relevant files
4. **Review logs periodically** - Monitor for unexpected activity
5. **Keep agentsh updated** - Get latest security fixes

### For Deployments

1. **Restrict shell access** - Only for authorized users
2. **Use secure API key management** - Vault, secrets manager
3. **Configure audit logging** - Send to central log system
4. **Set conservative safety defaults** - Err on side of caution
5. **Test in staging first** - Validate behavior before production

### For Enterprise

1. **Self-hosted LLM** - Keep data in your network
2. **Network segmentation** - Limit AI endpoint access
3. **Log aggregation** - Central security monitoring
4. **Incident response plan** - Know what to do if something goes wrong
5. **Regular security reviews** - Audit configurations and logs

## Vulnerability Reporting

Report security vulnerabilities to: security@yourdomain.com

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We aim to respond within 48 hours and will credit reporters in release notes (unless anonymity is requested).
