"""Tests for session memory."""

import pytest

from agentsh.memory.schemas import Turn, MemoryType
from agentsh.memory.session import (
    SessionConfig,
    SessionStore,
    MultiSessionStore,
)


class TestSessionConfig:
    """Tests for SessionConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SessionConfig()
        assert config.max_turns == 50
        assert config.max_tokens_estimate == 4000
        assert config.summarize_after == 20
        assert config.session_id  # Should have a UUID

    def test_custom_config(self):
        """Test custom configuration."""
        config = SessionConfig(
            max_turns=100,
            session_id="custom-id",
        )
        assert config.max_turns == 100
        assert config.session_id == "custom-id"


class TestSessionStore:
    """Tests for SessionStore."""

    @pytest.fixture
    def store(self):
        """Create a fresh session store."""
        return SessionStore()

    def test_init(self, store):
        """Test initialization."""
        assert store.turn_count == 0
        assert store.session_id is not None

    def test_append_turn(self, store):
        """Test appending turns."""
        turn = Turn(
            user_input="List files",
            agent_response="Here are the files...",
            tools_used=["fs.list"],
        )
        store.append_turn(turn)
        assert store.turn_count == 1

    def test_get_recent(self, store):
        """Test getting recent turns."""
        for i in range(5):
            turn = Turn(
                user_input=f"Request {i}",
                agent_response=f"Response {i}",
            )
            store.append_turn(turn)

        recent = store.get_recent(3)
        assert len(recent) == 3
        # Should be oldest to newest
        assert recent[0].user_input == "Request 2"
        assert recent[2].user_input == "Request 4"

    def test_get_all(self, store):
        """Test getting all turns."""
        for i in range(3):
            store.append_turn(Turn(
                user_input=f"Input {i}",
                agent_response=f"Output {i}",
            ))

        all_turns = store.get_all()
        assert len(all_turns) == 3

    def test_search(self, store):
        """Test searching turns."""
        store.append_turn(Turn(
            user_input="Tell me about Python",
            agent_response="Python is a programming language",
        ))
        store.append_turn(Turn(
            user_input="What about JavaScript?",
            agent_response="JavaScript is for web development",
        ))

        results = store.search("Python")
        assert len(results) == 1
        assert "Python" in results[0].user_input

    def test_summarize(self, store):
        """Test generating summary."""
        store.append_turn(Turn(
            user_input="List files",
            agent_response="Here are the files",
            tools_used=["fs.list"],
            success=True,
        ))
        store.append_turn(Turn(
            user_input="Read config",
            agent_response="Config contents",
            tools_used=["fs.read"],
            success=False,
        ))

        summary = store.summarize()
        assert "2 exchanges" in summary
        assert "1 successful" in summary
        assert "1 failed" in summary

    def test_summarize_empty(self, store):
        """Test summary of empty session."""
        summary = store.summarize()
        assert "No conversation" in summary

    def test_get_context_window(self, store):
        """Test getting formatted context."""
        store.append_turn(Turn(
            user_input="Hello",
            agent_response="Hi there!",
        ))

        context = store.get_context_window()
        assert "User: Hello" in context
        assert "Assistant: Hi there!" in context

    def test_clear(self, store):
        """Test clearing session."""
        store.append_turn(Turn(
            user_input="Test",
            agent_response="Response",
        ))
        assert store.turn_count == 1

        store.clear()
        assert store.turn_count == 0

    def test_to_memory_records(self, store):
        """Test converting turns to memory records."""
        store.append_turn(Turn(
            user_input="Test",
            agent_response="Response",
            tools_used=["test.tool"],
        ))

        records = store.to_memory_records()
        assert len(records) == 1
        assert records[0].type == MemoryType.CONVERSATION_TURN

    def test_max_turns_limit(self):
        """Test that max turns is respected."""
        config = SessionConfig(max_turns=3)
        store = SessionStore(config)

        for i in range(5):
            store.append_turn(Turn(
                user_input=f"Input {i}",
                agent_response=f"Output {i}",
            ))

        assert store.turn_count == 3
        # Should keep the most recent
        turns = store.get_all()
        assert turns[0].user_input == "Input 2"


class TestMultiSessionStore:
    """Tests for MultiSessionStore."""

    @pytest.fixture
    def multi_store(self):
        """Create a multi-session store."""
        return MultiSessionStore(max_sessions=3)

    def test_get_or_create(self, multi_store):
        """Test getting or creating sessions."""
        session1 = multi_store.get_or_create("session-1")
        session2 = multi_store.get_or_create("session-2")

        assert session1.session_id == "session-1"
        assert session2.session_id == "session-2"

    def test_get_existing(self, multi_store):
        """Test getting existing session."""
        session1 = multi_store.get_or_create("session-1")
        session1.append_turn(Turn(
            user_input="Test",
            agent_response="Response",
        ))

        # Get same session
        session1_again = multi_store.get_or_create("session-1")
        assert session1_again.turn_count == 1

    def test_get_nonexistent(self, multi_store):
        """Test getting nonexistent session."""
        session = multi_store.get("nonexistent")
        assert session is None

    def test_remove(self, multi_store):
        """Test removing a session."""
        multi_store.get_or_create("session-1")
        assert multi_store.remove("session-1") is True
        assert multi_store.get("session-1") is None
        assert multi_store.remove("session-1") is False

    def test_list_sessions(self, multi_store):
        """Test listing session IDs."""
        multi_store.get_or_create("a")
        multi_store.get_or_create("b")

        sessions = multi_store.list_sessions()
        assert "a" in sessions
        assert "b" in sessions

    def test_max_sessions_eviction(self, multi_store):
        """Test that oldest sessions are evicted."""
        multi_store.get_or_create("session-1")
        multi_store.get_or_create("session-2")
        multi_store.get_or_create("session-3")
        multi_store.get_or_create("session-4")  # Should evict session-1

        assert multi_store.get("session-1") is None
        assert multi_store.get("session-4") is not None

    def test_access_updates_order(self, multi_store):
        """Test that accessing a session updates its order."""
        multi_store.get_or_create("session-1")
        multi_store.get_or_create("session-2")
        multi_store.get_or_create("session-3")

        # Access session-1 again to make it recent
        multi_store.get_or_create("session-1")

        # Adding session-4 should evict session-2 (oldest)
        multi_store.get_or_create("session-4")

        assert multi_store.get("session-1") is not None
        assert multi_store.get("session-2") is None
