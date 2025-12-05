#!/bin/bash
set -e

# Install package in editable mode if pyproject.toml exists
if [ -f /app/pyproject.toml ]; then
    echo "Installing AgentSH in editable mode..."
    pip install -e /app[dev] --quiet
fi

# Add to /etc/shells if not present
AGENTSH_PATH="/usr/local/bin/agentsh"
if [ -x "$AGENTSH_PATH" ] && ! grep -q "^${AGENTSH_PATH}$" /etc/shells 2>/dev/null; then
    echo "$AGENTSH_PATH" >> /etc/shells
fi

exec "$@"
