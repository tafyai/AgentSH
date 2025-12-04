"""Session memory for conversation history."""

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from agentsh.memory.schemas import MemoryRecord, MemoryType, Turn
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SessionConfig:
    """Configuration for session memory.

    Attributes:
        max_turns: Maximum turns to keep in memory
        max_tokens_estimate: Estimated max tokens for context
        summarize_after: Summarize after this many turns
        session_id: Unique session identifier
    """

    max_turns: int = 50
    max_tokens_estimate: int = 4000
    summarize_after: int = 20
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class SessionStore:
    """In-memory store for conversation history.

    Maintains a rolling window of conversation turns with
    optional summarization for long conversations.

    Example:
        store = SessionStore()
        store.append_turn(Turn(
            user_input="List files",
            agent_response="Here are the files...",
            tools_used=["fs.list"],
        ))
        recent = store.get_recent(5)
    """

    def __init__(self, config: Optional[SessionConfig] = None) -> None:
        """Initialize session store.

        Args:
            config: Session configuration
        """
        self.config = config or SessionConfig()
        self._turns: deque[Turn] = deque(maxlen=self.config.max_turns)
        self._summaries: list[str] = []
        self._created_at = datetime.now()

        logger.debug(
            "SessionStore initialized",
            session_id=self.config.session_id,
            max_turns=self.config.max_turns,
        )

    @property
    def session_id(self) -> str:
        """Get the session ID."""
        return self.config.session_id

    @property
    def turn_count(self) -> int:
        """Get the number of turns."""
        return len(self._turns)

    def append_turn(self, turn: Turn) -> None:
        """Add a turn to the session.

        Args:
            turn: Conversation turn to add
        """
        self._turns.append(turn)

        logger.debug(
            "Turn appended",
            session_id=self.session_id,
            turn_count=self.turn_count,
            tools_used=turn.tools_used,
        )

        # Check if we need to summarize
        if self.turn_count >= self.config.summarize_after:
            self._maybe_summarize()

    def get_recent(self, n: int = 10) -> list[Turn]:
        """Get the most recent turns.

        Args:
            n: Number of turns to retrieve

        Returns:
            List of recent turns (oldest first)
        """
        turns = list(self._turns)
        return turns[-n:] if len(turns) > n else turns

    def get_all(self) -> list[Turn]:
        """Get all turns in the session.

        Returns:
            List of all turns (oldest first)
        """
        return list(self._turns)

    def get_context_window(self, max_tokens: Optional[int] = None) -> str:
        """Get formatted context for LLM.

        Formats the conversation history for inclusion in an LLM prompt,
        respecting token limits.

        Args:
            max_tokens: Maximum estimated tokens (uses config default if None)

        Returns:
            Formatted conversation context
        """
        max_tokens = max_tokens or self.config.max_tokens_estimate

        # Start with summaries if any
        parts = []
        if self._summaries:
            parts.append("Previous conversation summary:")
            parts.extend(self._summaries)
            parts.append("")

        # Add recent turns
        parts.append("Recent conversation:")
        for turn in self._turns:
            turn_text = f"User: {turn.user_input}\nAssistant: {turn.agent_response}"
            parts.append(turn_text)

        context = "\n\n".join(parts)

        # Rough token estimate (4 chars per token)
        estimated_tokens = len(context) // 4

        # Truncate if needed
        if estimated_tokens > max_tokens:
            # Keep only the most recent turns
            char_limit = max_tokens * 4
            context = context[-char_limit:]
            # Find first complete turn
            first_user = context.find("User:")
            if first_user > 0:
                context = context[first_user:]

        return context

    def search(self, query: str, limit: int = 5) -> list[Turn]:
        """Search turns for a query.

        Simple keyword search through conversation history.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching turns
        """
        query_lower = query.lower()
        matches = []

        for turn in self._turns:
            if (
                query_lower in turn.user_input.lower()
                or query_lower in turn.agent_response.lower()
            ):
                matches.append(turn)

        return matches[:limit]

    def summarize(self) -> str:
        """Generate a summary of the conversation.

        Returns:
            Text summary of the conversation
        """
        if not self._turns:
            return "No conversation yet."

        # Build a simple summary
        topics = set()
        tools = set()
        successes = 0
        failures = 0

        for turn in self._turns:
            # Extract topics from user input
            words = turn.user_input.lower().split()
            topics.update(w for w in words if len(w) > 4)
            tools.update(turn.tools_used)

            if turn.success:
                successes += 1
            else:
                failures += 1

        summary_parts = [
            f"Session with {self.turn_count} exchanges.",
            f"Tools used: {', '.join(sorted(tools)) if tools else 'none'}.",
            f"Outcomes: {successes} successful, {failures} failed.",
        ]

        if topics:
            # Limit topics
            top_topics = sorted(topics)[:10]
            summary_parts.append(f"Topics discussed: {', '.join(top_topics)}.")

        return " ".join(summary_parts)

    def clear(self) -> None:
        """Clear all turns from the session."""
        self._turns.clear()
        self._summaries.clear()
        logger.debug("Session cleared", session_id=self.session_id)

    def to_memory_records(self) -> list[MemoryRecord]:
        """Convert all turns to memory records.

        Returns:
            List of MemoryRecord objects
        """
        return [turn.to_memory_record(self.session_id) for turn in self._turns]

    def _maybe_summarize(self) -> None:
        """Summarize old turns if needed."""
        if self.turn_count < self.config.summarize_after:
            return

        # Get turns to summarize (older half)
        turns_list = list(self._turns)
        summarize_count = self.turn_count // 2

        if summarize_count < 5:
            return

        # Generate summary of old turns
        old_turns = turns_list[:summarize_count]
        summary = self._generate_turn_summary(old_turns)
        self._summaries.append(summary)

        # Remove summarized turns
        for _ in range(summarize_count):
            self._turns.popleft()

        logger.debug(
            "Turns summarized",
            session_id=self.session_id,
            summarized_count=summarize_count,
            remaining_count=self.turn_count,
        )

    def _generate_turn_summary(self, turns: list[Turn]) -> str:
        """Generate a summary of specific turns.

        Args:
            turns: Turns to summarize

        Returns:
            Summary text
        """
        if not turns:
            return ""

        # Simple extractive summary
        topics = []
        for turn in turns:
            # Take first sentence of each user input
            first_sentence = turn.user_input.split(".")[0]
            if len(first_sentence) > 10:
                topics.append(first_sentence)

        if topics:
            return f"Earlier in the conversation, discussed: {'; '.join(topics[:5])}"
        return f"Earlier conversation with {len(turns)} exchanges."


class MultiSessionStore:
    """Manages multiple session stores.

    Useful for tracking conversations across different contexts
    or users.
    """

    def __init__(self, max_sessions: int = 10) -> None:
        """Initialize multi-session store.

        Args:
            max_sessions: Maximum concurrent sessions
        """
        self._sessions: dict[str, SessionStore] = {}
        self._max_sessions = max_sessions
        self._access_order: list[str] = []

    def get_or_create(self, session_id: str) -> SessionStore:
        """Get or create a session store.

        Args:
            session_id: Session identifier

        Returns:
            SessionStore for the session
        """
        if session_id not in self._sessions:
            # Evict oldest if at capacity
            if len(self._sessions) >= self._max_sessions:
                oldest = self._access_order.pop(0)
                del self._sessions[oldest]

            config = SessionConfig(session_id=session_id)
            self._sessions[session_id] = SessionStore(config)

        # Update access order
        if session_id in self._access_order:
            self._access_order.remove(session_id)
        self._access_order.append(session_id)

        return self._sessions[session_id]

    def get(self, session_id: str) -> Optional[SessionStore]:
        """Get a session store if it exists.

        Args:
            session_id: Session identifier

        Returns:
            SessionStore or None
        """
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> bool:
        """Remove a session.

        Args:
            session_id: Session identifier

        Returns:
            True if removed, False if not found
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._access_order.remove(session_id)
            return True
        return False

    def list_sessions(self) -> list[str]:
        """List all session IDs.

        Returns:
            List of session IDs
        """
        return list(self._sessions.keys())
