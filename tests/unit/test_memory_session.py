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


class TestSessionStoreSummarization:
    """Tests for session summarization behavior."""

    def test_maybe_summarize_triggers_after_threshold(self):
        """Test that summarization triggers after threshold."""
        config = SessionConfig(
            summarize_after=10,
            max_turns=50,
        )
        store = SessionStore(config)

        # Add turns to trigger summarization
        for i in range(15):
            store.append_turn(Turn(
                user_input=f"This is a longer user input number {i}",
                agent_response=f"This is the agent response for input {i}",
            ))

        # Should have triggered summarization
        # The summarized turns should be removed, replaced with summary
        # After summarizing half (7 turns), we should have 8 remaining
        assert store.turn_count < 15  # Some turns were summarized

    def test_generate_turn_summary_with_topics(self):
        """Test turn summary generation extracts topics."""
        store = SessionStore()

        # Manually test _generate_turn_summary
        turns = [
            Turn(
                user_input="Please analyze the Python code structure.",
                agent_response="Here's the analysis.",
            ),
            Turn(
                user_input="Now check the JavaScript files.",
                agent_response="Checking files.",
            ),
        ]

        summary = store._generate_turn_summary(turns)
        assert "Earlier" in summary
        assert "conversation" in summary.lower() or "discussed" in summary.lower()

    def test_generate_turn_summary_empty(self):
        """Test turn summary with empty list."""
        store = SessionStore()
        summary = store._generate_turn_summary([])
        assert summary == ""

    def test_generate_turn_summary_short_inputs(self):
        """Test turn summary with short inputs."""
        store = SessionStore()
        turns = [
            Turn(
                user_input="Hi",  # Too short to be included
                agent_response="Hello",
            ),
            Turn(
                user_input="Bye",  # Too short
                agent_response="Goodbye",
            ),
        ]

        summary = store._generate_turn_summary(turns)
        # With short inputs, falls back to "Earlier conversation" format
        assert "Earlier" in summary

    def test_get_context_window_with_summaries(self):
        """Test context window includes summaries."""
        config = SessionConfig(
            summarize_after=6,
            max_turns=50,
        )
        store = SessionStore(config)

        # Add enough turns to trigger summarization
        for i in range(15):
            store.append_turn(Turn(
                user_input=f"This is user input number {i}",
                agent_response=f"This is response number {i}",
            ))

        context = store.get_context_window()

        # Should include both summary and recent turns
        assert "Recent conversation" in context
        # If summarization happened, should have summary
        if store._summaries:
            assert "Previous conversation summary" in context

    def test_get_context_window_truncation(self):
        """Test context window respects token limits."""
        store = SessionStore()

        # Add many long turns
        for i in range(20):
            long_text = f"This is a very long message {i}. " * 50
            store.append_turn(Turn(
                user_input=long_text,
                agent_response=long_text,
            ))

        # Request a small context window (100 tokens = ~400 chars)
        context = store.get_context_window(max_tokens=100)

        # Should be truncated to around max_tokens * 4 characters
        assert len(context) <= 500  # Some slack for finding complete turns

    def test_context_window_truncation_finds_complete_turn(self):
        """Test truncation finds a complete turn boundary."""
        store = SessionStore()

        # Add several turns
        for i in range(5):
            store.append_turn(Turn(
                user_input=f"User message {i} " * 20,
                agent_response=f"Response {i} " * 20,
            ))

        # Request very small context
        context = store.get_context_window(max_tokens=50)

        # Should start with "User:" after truncation
        if "User:" in context:
            assert context.index("User:") == 0 or context.startswith("Recent")


class TestSessionStoreEdgeCases:
    """Edge case tests for SessionStore."""

    def test_get_recent_more_than_available(self):
        """Test getting more turns than available."""
        store = SessionStore()
        store.append_turn(Turn(
            user_input="Only one",
            agent_response="Single response",
        ))

        recent = store.get_recent(100)
        assert len(recent) == 1

    def test_search_in_response(self):
        """Test search finds matches in responses."""
        store = SessionStore()
        store.append_turn(Turn(
            user_input="What time is it?",
            agent_response="The current time is 3:00 PM",
        ))

        results = store.search("3:00 PM")
        assert len(results) == 1

    def test_search_case_insensitive(self):
        """Test search is case insensitive."""
        store = SessionStore()
        store.append_turn(Turn(
            user_input="UPPERCASE query",
            agent_response="lowercase response",
        ))

        results = store.search("uppercase")
        assert len(results) == 1

        results = store.search("LOWERCASE")
        assert len(results) == 1

    def test_search_limit(self):
        """Test search respects limit."""
        store = SessionStore()

        # Add multiple matching turns
        for i in range(10):
            store.append_turn(Turn(
                user_input=f"Python question {i}",
                agent_response=f"Answer {i}",
            ))

        results = store.search("Python", limit=3)
        assert len(results) == 3

    def test_summarize_with_topics(self):
        """Test summary includes topics from longer words."""
        store = SessionStore()
        store.append_turn(Turn(
            user_input="kubernetes deployment strategy",
            agent_response="Here's the deployment plan",
            tools_used=["kubectl.apply"],
            success=True,
        ))

        summary = store.summarize()
        assert "kubernetes" in summary or "Topics discussed:" in summary

    def test_summarize_tools_list(self):
        """Test summary lists unique tools."""
        store = SessionStore()
        store.append_turn(Turn(
            user_input="Read file",
            agent_response="Contents",
            tools_used=["fs.read"],
            success=True,
        ))
        store.append_turn(Turn(
            user_input="Read another",
            agent_response="More contents",
            tools_used=["fs.read"],  # Same tool
            success=True,
        ))

        summary = store.summarize()
        # Should only list unique tools
        assert summary.count("fs.read") == 1
