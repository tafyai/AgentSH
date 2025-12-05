"""Tests for agent prompts module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from agentsh.agent.prompts import (
    SYSTEM_PROMPT_TEMPLATE,
    FEW_SHOT_EXAMPLES,
    CODE_REVIEW_PROMPT,
    DEBUGGING_PROMPT,
    REFACTORING_PROMPT,
    build_system_prompt,
    build_few_shot_messages,
)


class TestSystemPromptTemplate:
    """Tests for the system prompt template."""

    def test_template_has_context_placeholder(self) -> None:
        """Template should have context placeholder."""
        assert "{context}" in SYSTEM_PROMPT_TEMPLATE

    def test_template_has_tools_placeholder(self) -> None:
        """Template should have tools placeholder."""
        assert "{available_tools}" in SYSTEM_PROMPT_TEMPLATE

    def test_template_mentions_capabilities(self) -> None:
        """Template should mention agent capabilities."""
        assert "Execute shell commands" in SYSTEM_PROMPT_TEMPLATE
        assert "Read and modify files" in SYSTEM_PROMPT_TEMPLATE

    def test_template_mentions_safety_rules(self) -> None:
        """Template should mention safety rules."""
        assert "Safety Rules" in SYSTEM_PROMPT_TEMPLATE
        assert "Never execute destructive commands" in SYSTEM_PROMPT_TEMPLATE


class TestFewShotExamples:
    """Tests for few-shot examples."""

    def test_examples_exist(self) -> None:
        """Should have few-shot examples."""
        assert len(FEW_SHOT_EXAMPLES) > 0

    def test_examples_have_required_keys(self) -> None:
        """Each example should have user and assistant keys."""
        for example in FEW_SHOT_EXAMPLES:
            assert "user" in example
            assert "assistant" in example

    def test_examples_are_non_empty(self) -> None:
        """Examples should have non-empty content."""
        for example in FEW_SHOT_EXAMPLES:
            assert len(example["user"]) > 0
            assert len(example["assistant"]) > 0


class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""

    def test_basic_prompt(self) -> None:
        """Should build prompt with basic inputs."""
        prompt = build_system_prompt(
            available_tools=["shell.run", "file.read"],
        )

        assert "shell.run" in prompt
        assert "file.read" in prompt
        assert "Current directory:" in prompt

    def test_prompt_with_cwd(self) -> None:
        """Should include provided cwd."""
        prompt = build_system_prompt(
            available_tools=["test"],
            cwd="/home/test/project",
        )

        assert "/home/test/project" in prompt

    def test_prompt_default_cwd(self) -> None:
        """Should use current directory as default cwd."""
        prompt = build_system_prompt(
            available_tools=["test"],
        )

        # Should contain current working directory
        assert str(Path.cwd()) in prompt

    def test_prompt_with_os_info(self) -> None:
        """Should include provided OS info."""
        prompt = build_system_prompt(
            available_tools=["test"],
            os_info="Linux 5.10.0",
        )

        assert "Linux 5.10.0" in prompt

    def test_prompt_default_os_info(self) -> None:
        """Should use platform info as default."""
        import platform

        prompt = build_system_prompt(
            available_tools=["test"],
        )

        # Should contain operating system info
        assert "Operating system:" in prompt

    def test_prompt_with_shell(self) -> None:
        """Should include provided shell."""
        prompt = build_system_prompt(
            available_tools=["test"],
            shell="/usr/bin/zsh",
        )

        assert "zsh" in prompt

    def test_prompt_default_shell(self) -> None:
        """Should use SHELL env var as default."""
        with patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            prompt = build_system_prompt(
                available_tools=["test"],
            )

            assert "bash" in prompt

    def test_prompt_unknown_shell(self) -> None:
        """Should handle unknown shell."""
        with patch.dict(os.environ, {"SHELL": ""}, clear=True):
            prompt = build_system_prompt(
                available_tools=["test"],
                shell="",
            )

            assert "Shell:" in prompt

    def test_prompt_with_recent_history(self) -> None:
        """Should include recent history."""
        history = ["ls -la", "cd /tmp", "pwd"]
        prompt = build_system_prompt(
            available_tools=["test"],
            recent_history=history,
        )

        assert "Recent commands:" in prompt
        assert "ls -la" in prompt
        assert "cd /tmp" in prompt
        assert "pwd" in prompt

    def test_prompt_history_limited_to_five(self) -> None:
        """Should only show last 5 commands."""
        history = ["cmd1", "cmd2", "cmd3", "cmd4", "cmd5", "cmd6", "cmd7"]
        prompt = build_system_prompt(
            available_tools=["test"],
            recent_history=history,
        )

        # Should have last 5 commands
        assert "cmd3" in prompt
        assert "cmd4" in prompt
        assert "cmd5" in prompt
        assert "cmd6" in prompt
        assert "cmd7" in prompt
        # Should not have first two
        assert "cmd1" not in prompt
        assert "cmd2" not in prompt

    def test_prompt_no_history(self) -> None:
        """Should work without history."""
        prompt = build_system_prompt(
            available_tools=["test"],
            recent_history=None,
        )

        assert "Recent commands:" not in prompt

    def test_prompt_empty_history(self) -> None:
        """Should work with empty history list."""
        prompt = build_system_prompt(
            available_tools=["test"],
            recent_history=[],
        )

        # Empty list is falsy, so no history section
        assert "Recent commands:" not in prompt

    def test_prompt_empty_tools_list(self) -> None:
        """Should handle empty tools list."""
        prompt = build_system_prompt(
            available_tools=[],
        )

        assert "No tools available." in prompt

    def test_prompt_includes_datetime(self) -> None:
        """Should include current time."""
        prompt = build_system_prompt(
            available_tools=["test"],
        )

        assert "Current time:" in prompt


class TestBuildFewShotMessages:
    """Tests for build_few_shot_messages function."""

    def test_returns_list(self) -> None:
        """Should return a list of messages."""
        messages = build_few_shot_messages()
        assert isinstance(messages, list)

    def test_messages_have_role_and_content(self) -> None:
        """Each message should have role and content."""
        messages = build_few_shot_messages()
        for msg in messages:
            assert "role" in msg
            assert "content" in msg

    def test_messages_alternate_user_assistant(self) -> None:
        """Messages should alternate between user and assistant."""
        messages = build_few_shot_messages()

        for i, msg in enumerate(messages):
            expected_role = "user" if i % 2 == 0 else "assistant"
            assert msg["role"] == expected_role

    def test_message_count_is_double_examples(self) -> None:
        """Should have two messages per example."""
        messages = build_few_shot_messages()
        assert len(messages) == len(FEW_SHOT_EXAMPLES) * 2

    def test_messages_match_examples(self) -> None:
        """Messages should match the few-shot examples."""
        messages = build_few_shot_messages()

        for i, example in enumerate(FEW_SHOT_EXAMPLES):
            user_msg = messages[i * 2]
            assistant_msg = messages[i * 2 + 1]

            assert user_msg["content"] == example["user"]
            assert assistant_msg["content"] == example["assistant"]


class TestSpecializedPrompts:
    """Tests for specialized prompt templates."""

    def test_code_review_prompt_exists(self) -> None:
        """Code review prompt should exist."""
        assert len(CODE_REVIEW_PROMPT) > 0
        assert "reviewing code" in CODE_REVIEW_PROMPT.lower()

    def test_code_review_mentions_key_areas(self) -> None:
        """Code review prompt should mention key areas."""
        assert "Logic errors" in CODE_REVIEW_PROMPT
        assert "Security vulnerabilities" in CODE_REVIEW_PROMPT
        assert "Performance" in CODE_REVIEW_PROMPT

    def test_debugging_prompt_exists(self) -> None:
        """Debugging prompt should exist."""
        assert len(DEBUGGING_PROMPT) > 0
        assert "debug" in DEBUGGING_PROMPT.lower()

    def test_debugging_prompt_mentions_approach(self) -> None:
        """Debugging prompt should mention systematic approach."""
        assert "error" in DEBUGGING_PROMPT.lower()
        assert "diagnostic" in DEBUGGING_PROMPT.lower()
        assert "solutions" in DEBUGGING_PROMPT.lower()

    def test_refactoring_prompt_exists(self) -> None:
        """Refactoring prompt should exist."""
        assert len(REFACTORING_PROMPT) > 0
        assert "refactor" in REFACTORING_PROMPT.lower()

    def test_refactoring_prompt_mentions_principles(self) -> None:
        """Refactoring prompt should mention key principles."""
        assert "Maintain existing behavior" in REFACTORING_PROMPT
        assert "readability" in REFACTORING_PROMPT.lower()
        assert "tests" in REFACTORING_PROMPT.lower()
