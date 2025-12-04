"""Tests for help system module."""

import pytest

from agentsh.shell.help import (
    HelpCategory,
    HelpSystem,
    HelpTopic,
    get_help_system,
    show_help,
)


class TestHelpTopic:
    """Tests for HelpTopic dataclass."""

    def test_create_topic(self) -> None:
        """Should create topic with required fields."""
        topic = HelpTopic(
            name="test",
            title="Test Topic",
            category=HelpCategory.COMMANDS,
            summary="A test topic",
            content="Test content here.",
        )

        assert topic.name == "test"
        assert topic.title == "Test Topic"
        assert topic.summary == "A test topic"
        assert topic.content == "Test content here."

    def test_topic_with_aliases(self) -> None:
        """Should support aliases."""
        topic = HelpTopic(
            name="test",
            title="Test",
            category=HelpCategory.COMMANDS,
            summary="Test",
            content="Content",
            aliases=["t", "tst"],
        )

        assert "t" in topic.aliases
        assert "tst" in topic.aliases

    def test_topic_with_see_also(self) -> None:
        """Should support see_also references."""
        topic = HelpTopic(
            name="test",
            title="Test",
            category=HelpCategory.COMMANDS,
            summary="Test",
            content="Content",
            see_also=["other", "related"],
        )

        assert "other" in topic.see_also
        assert "related" in topic.see_also


class TestHelpSystem:
    """Tests for HelpSystem class."""

    @pytest.fixture
    def help_system(self) -> HelpSystem:
        """Create help system instance."""
        return HelpSystem()

    def test_builtin_topics_registered(self, help_system: HelpSystem) -> None:
        """Should have builtin topics registered."""
        # Check some expected topics
        assert help_system.get("intro") is not None
        assert help_system.get("commands") is not None
        assert help_system.get("ai") is not None
        assert help_system.get("security") is not None

    def test_get_by_name(self, help_system: HelpSystem) -> None:
        """Should get topic by name."""
        topic = help_system.get("commands")

        assert topic is not None
        assert topic.name == "commands"
        assert topic.category == HelpCategory.COMMANDS

    def test_get_by_alias(self, help_system: HelpSystem) -> None:
        """Should get topic by alias."""
        # 'cmds' is an alias for 'commands'
        topic = help_system.get("cmds")

        assert topic is not None
        assert topic.name == "commands"

    def test_get_case_insensitive(self, help_system: HelpSystem) -> None:
        """Should get topic case-insensitively."""
        topic = help_system.get("COMMANDS")

        assert topic is not None
        assert topic.name == "commands"

    def test_get_not_found(self, help_system: HelpSystem) -> None:
        """Should return None for unknown topic."""
        topic = help_system.get("nonexistent")
        assert topic is None

    def test_register_custom_topic(self, help_system: HelpSystem) -> None:
        """Should register custom topics."""
        custom = HelpTopic(
            name="custom",
            title="Custom Topic",
            category=HelpCategory.COMMANDS,
            summary="A custom topic",
            content="Custom content",
            aliases=["cust"],
        )

        help_system.register(custom)

        # Get by name
        assert help_system.get("custom") is not None
        # Get by alias
        assert help_system.get("cust") is not None

    def test_list_topics(self, help_system: HelpSystem) -> None:
        """Should list all topics."""
        topics = help_system.list_topics()

        assert len(topics) > 0
        assert all(isinstance(t, HelpTopic) for t in topics)

    def test_list_topics_by_category(self, help_system: HelpSystem) -> None:
        """Should filter by category."""
        commands = help_system.list_topics(HelpCategory.COMMANDS)

        assert len(commands) > 0
        assert all(t.category == HelpCategory.COMMANDS for t in commands)

    def test_search(self, help_system: HelpSystem) -> None:
        """Should search topics."""
        results = help_system.search("ai")

        assert len(results) > 0
        # AI topic should be in results
        names = [t.name for t in results]
        assert "ai" in names

    def test_search_in_content(self, help_system: HelpSystem) -> None:
        """Should search in topic content."""
        results = help_system.search("natural language")

        assert len(results) > 0

    def test_search_no_results(self, help_system: HelpSystem) -> None:
        """Should return empty list for no matches."""
        results = help_system.search("xyznonexistent123")
        assert results == []

    def test_format_topic(self, help_system: HelpSystem) -> None:
        """Should format topic for display."""
        topic = help_system.get("commands")
        formatted = help_system.format_topic(topic, use_color=False)

        assert "Special Commands" in formatted
        assert topic.summary in formatted

    def test_format_topic_with_see_also(self, help_system: HelpSystem) -> None:
        """Should include see also section."""
        topic = help_system.get("intro")
        formatted = help_system.format_topic(topic, use_color=False)

        assert "See also" in formatted

    def test_format_overview(self, help_system: HelpSystem) -> None:
        """Should format help overview."""
        overview = help_system.format_overview(use_color=False)

        assert "AgentSH Help" in overview
        assert ":help <topic>" in overview

    def test_format_topic_list(self, help_system: HelpSystem) -> None:
        """Should format topic list."""
        topic_list = help_system.format_topic_list(use_color=False)

        assert "All Help Topics" in topic_list
        assert "commands" in topic_list

    def test_show_overview(self, help_system: HelpSystem) -> None:
        """Should show overview when no topic specified."""
        output = help_system.show(use_color=False)

        assert "AgentSH Help" in output

    def test_show_topic(self, help_system: HelpSystem) -> None:
        """Should show specific topic."""
        output = help_system.show("commands", use_color=False)

        assert "Special Commands" in output

    def test_show_all(self, help_system: HelpSystem) -> None:
        """Should show all topics with 'all'."""
        output = help_system.show("all", use_color=False)

        assert "All Help Topics" in output

    def test_show_not_found_suggests(self, help_system: HelpSystem) -> None:
        """Should suggest similar topics when not found."""
        output = help_system.show("cmd", use_color=False)

        # Should suggest 'commands' since 'cmd' is close
        assert "commands" in output.lower() or "Did you mean" in output

    def test_show_not_found_no_suggestions(self, help_system: HelpSystem) -> None:
        """Should show error when no similar topics."""
        output = help_system.show("xyznonexistent123", use_color=False)

        assert "No help topic found" in output


class TestGlobalHelpSystem:
    """Tests for global help system functions."""

    def test_get_help_system_singleton(self) -> None:
        """Should return same instance."""
        system1 = get_help_system()
        system2 = get_help_system()

        assert system1 is system2

    def test_show_help_function(self) -> None:
        """Should show help via convenience function."""
        output = show_help(use_color=False)

        assert "AgentSH Help" in output

    def test_show_help_topic(self) -> None:
        """Should show topic via convenience function."""
        output = show_help("commands", use_color=False)

        assert "Special Commands" in output


class TestHelpCategories:
    """Tests for help categories."""

    def test_all_categories_have_topics(self) -> None:
        """Should have topics in all categories."""
        help_system = HelpSystem()

        for category in HelpCategory:
            topics = help_system.list_topics(category)
            assert len(topics) > 0, f"No topics in category {category}"

    def test_category_values(self) -> None:
        """Should have expected categories."""
        categories = list(HelpCategory)

        assert HelpCategory.GETTING_STARTED in categories
        assert HelpCategory.COMMANDS in categories
        assert HelpCategory.AI in categories
        assert HelpCategory.SECURITY in categories
        assert HelpCategory.TROUBLESHOOTING in categories
