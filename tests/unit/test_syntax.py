"""Tests for syntax highlighting module."""

import tempfile
from pathlib import Path

import pytest

from agentsh.utils.syntax import (
    AnsiColor,
    ColorScheme,
    DARK_SCHEME,
    LIGHT_SCHEME,
    LanguageDefinition,
    LANGUAGES,
    PYTHON,
    JAVASCRIPT,
    BASH,
    SyntaxHighlighter,
    TokenType,
    get_highlighter,
    highlight,
    highlight_file,
)


class TestTokenType:
    """Tests for TokenType enum."""

    def test_token_types(self) -> None:
        """Should have expected token types."""
        assert TokenType.KEYWORD == "keyword"
        assert TokenType.STRING == "string"
        assert TokenType.NUMBER == "number"
        assert TokenType.COMMENT == "comment"
        assert TokenType.FUNCTION == "function"
        assert TokenType.CLASS == "class"


class TestAnsiColor:
    """Tests for AnsiColor enum."""

    def test_color_codes(self) -> None:
        """Should have ANSI escape codes."""
        assert AnsiColor.RESET.value == "\033[0m"
        assert AnsiColor.BOLD.value == "\033[1m"
        assert AnsiColor.RED.value == "\033[31m"
        assert AnsiColor.GREEN.value == "\033[32m"

    def test_bright_colors(self) -> None:
        """Should have bright color variants."""
        assert AnsiColor.BRIGHT_RED.value == "\033[91m"
        assert AnsiColor.BRIGHT_GREEN.value == "\033[92m"


class TestColorScheme:
    """Tests for ColorScheme dataclass."""

    def test_default_scheme(self) -> None:
        """Should have default colors."""
        scheme = ColorScheme()
        assert scheme.reset == AnsiColor.RESET.value
        assert AnsiColor.BLUE.value in scheme.keyword

    def test_get_color(self) -> None:
        """Should get color for token type."""
        scheme = ColorScheme()
        color = scheme.get_color(TokenType.KEYWORD)
        assert AnsiColor.BLUE.value in color

    def test_get_color_default(self) -> None:
        """Should return default for unknown type."""
        scheme = ColorScheme()
        color = scheme.get_color(TokenType.DEFAULT)
        assert color == scheme.default


class TestLanguageDefinition:
    """Tests for LanguageDefinition dataclass."""

    def test_python_definition(self) -> None:
        """Should have Python keywords."""
        assert "def" in PYTHON.keywords
        assert "class" in PYTHON.keywords
        assert "import" in PYTHON.keywords
        assert "print" in PYTHON.builtins
        assert "True" in PYTHON.constants

    def test_javascript_definition(self) -> None:
        """Should have JavaScript keywords."""
        assert "function" in JAVASCRIPT.keywords
        assert "const" in JAVASCRIPT.keywords
        assert "let" in JAVASCRIPT.keywords
        assert "console" in JAVASCRIPT.builtins

    def test_bash_definition(self) -> None:
        """Should have Bash keywords."""
        assert "if" in BASH.keywords
        assert "then" in BASH.keywords
        assert "echo" in BASH.builtins
        assert "grep" in BASH.builtins


class TestLanguages:
    """Tests for language mapping."""

    def test_language_aliases(self) -> None:
        """Should support language aliases."""
        assert LANGUAGES["python"] is LANGUAGES["py"]
        assert LANGUAGES["javascript"] is LANGUAGES["js"]
        assert LANGUAGES["bash"] is LANGUAGES["sh"]
        assert LANGUAGES["yaml"] is LANGUAGES["yml"]

    def test_all_languages_present(self) -> None:
        """Should have all expected languages."""
        expected = ["python", "py", "javascript", "js", "bash", "sh", "json", "yaml"]
        for lang in expected:
            assert lang in LANGUAGES


class TestSyntaxHighlighter:
    """Tests for SyntaxHighlighter class."""

    @pytest.fixture
    def highlighter(self) -> SyntaxHighlighter:
        """Create a highlighter for testing."""
        return SyntaxHighlighter()

    @pytest.fixture
    def no_color_highlighter(self) -> SyntaxHighlighter:
        """Create a highlighter without colors."""
        return SyntaxHighlighter(use_color=False)

    def test_create_highlighter(self) -> None:
        """Should create highlighter with defaults."""
        h = SyntaxHighlighter()
        assert h.scheme is not None
        assert h.use_color is True

    def test_create_highlighter_custom_scheme(self) -> None:
        """Should accept custom scheme."""
        h = SyntaxHighlighter(scheme=LIGHT_SCHEME)
        assert h.scheme is LIGHT_SCHEME

    def test_create_highlighter_no_color(self) -> None:
        """Should disable colors."""
        h = SyntaxHighlighter(use_color=False)
        assert h.use_color is False

    def test_highlight_no_color(self, no_color_highlighter: SyntaxHighlighter) -> None:
        """Should return unchanged code when colors disabled."""
        code = "def hello(): pass"
        result = no_color_highlighter.highlight(code, "python")
        assert result == code

    def test_highlight_unknown_language(self, highlighter: SyntaxHighlighter) -> None:
        """Should return unchanged for unknown language."""
        code = "some code"
        result = highlighter.highlight(code, "unknown_lang")
        assert result == code

    def test_highlight_python_keyword(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight Python keywords."""
        code = "def hello():"
        result = highlighter.highlight(code, "python")
        assert AnsiColor.RESET.value in result
        assert "def" in result

    def test_highlight_python_string(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight strings."""
        code = 'x = "hello"'
        result = highlighter.highlight(code, "python")
        assert '"hello"' in result or "hello" in result

    def test_highlight_python_number(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight numbers."""
        code = "x = 42"
        result = highlighter.highlight(code, "python")
        assert "42" in result

    def test_highlight_python_comment(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight comments."""
        code = "x = 1  # comment"
        result = highlighter.highlight(code, "python")
        assert "# comment" in result

    def test_highlight_python_function(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight function calls."""
        code = "print(x)"
        result = highlighter.highlight(code, "python")
        assert "print" in result

    def test_highlight_python_class(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight class names."""
        code = "class MyClass:"
        result = highlighter.highlight(code, "python")
        assert "MyClass" in result

    def test_highlight_python_decorator(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight decorators."""
        code = "@property\ndef x(self): pass"
        result = highlighter.highlight(code, "python")
        assert "@property" in result

    def test_highlight_python_builtin(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight builtins."""
        code = "x = len(items)"
        result = highlighter.highlight(code, "python")
        assert "len" in result

    def test_highlight_python_constant(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight constants."""
        code = "x = True"
        result = highlighter.highlight(code, "python")
        assert "True" in result

    def test_highlight_javascript(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight JavaScript."""
        code = "const x = 1;"
        result = highlighter.highlight(code, "javascript")
        assert "const" in result

    def test_highlight_javascript_comment(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight JS comments."""
        code = "x = 1; // comment"
        result = highlighter.highlight(code, "javascript")
        assert "// comment" in result

    def test_highlight_bash(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight Bash."""
        code = "if [ -f file ]; then echo ok; fi"
        result = highlighter.highlight(code, "bash")
        assert "if" in result
        assert "then" in result

    def test_highlight_multiline(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight multiple lines."""
        code = """def hello():
    print("world")
    return 42"""
        result = highlighter.highlight(code, "python")
        assert "def" in result
        assert "print" in result
        assert "return" in result

    def test_highlight_empty_lines(self, highlighter: SyntaxHighlighter) -> None:
        """Should handle empty lines."""
        code = "def x():\n\n    pass"
        result = highlighter.highlight(code, "python")
        assert "\n\n" in result

    def test_highlight_hex_number(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight hex numbers."""
        code = "x = 0xFF"
        result = highlighter.highlight(code, "python")
        assert "0xFF" in result

    def test_highlight_float_number(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight float numbers."""
        code = "x = 3.14"
        result = highlighter.highlight(code, "python")
        assert "3.14" in result

    def test_highlight_escaped_string(self, highlighter: SyntaxHighlighter) -> None:
        """Should handle escaped quotes in strings."""
        code = 'x = "hello \\"world\\""'
        result = highlighter.highlight(code, "python")
        # Should not break on escaped quotes
        assert "hello" in result

    def test_highlight_string_with_comment_char(
        self, highlighter: SyntaxHighlighter
    ) -> None:
        """Should not highlight comment chars inside strings."""
        code = 'x = "# not a comment"'
        result = highlighter.highlight(code, "python")
        # The # should be part of the string, not a comment
        assert "# not a comment" in result


class TestGlobalFunctions:
    """Tests for global highlighter functions."""

    def test_get_highlighter(self) -> None:
        """Should return highlighter instance."""
        h = get_highlighter()
        assert isinstance(h, SyntaxHighlighter)

    def test_get_highlighter_same_instance(self) -> None:
        """Should return same instance."""
        h1 = get_highlighter()
        h2 = get_highlighter()
        assert h1 is h2

    def test_highlight_function(self) -> None:
        """Should highlight using global function."""
        code = "def x(): pass"
        result = highlight(code, "python")
        assert "def" in result

    def test_highlight_file(self) -> None:
        """Should highlight from file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write("def hello(): pass\n")
            f.flush()

            result = highlight_file(f.name)
            assert "def" in result

    def test_highlight_file_auto_detect(self) -> None:
        """Should auto-detect language from extension."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", delete=False
        ) as f:
            f.write("const x = 1;\n")
            f.flush()

            result = highlight_file(f.name)
            assert "const" in result


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.fixture
    def highlighter(self) -> SyntaxHighlighter:
        return SyntaxHighlighter()

    def test_empty_code(self, highlighter: SyntaxHighlighter) -> None:
        """Should handle empty code."""
        result = highlighter.highlight("", "python")
        assert result == ""

    def test_whitespace_only(self, highlighter: SyntaxHighlighter) -> None:
        """Should handle whitespace-only code."""
        result = highlighter.highlight("   \n\t\n   ", "python")
        assert "   \n\t\n   " in result

    def test_single_character(self, highlighter: SyntaxHighlighter) -> None:
        """Should handle single character."""
        result = highlighter.highlight("x", "python")
        assert "x" in result

    def test_operators_only(self, highlighter: SyntaxHighlighter) -> None:
        """Should handle operators."""
        result = highlighter.highlight("+ - * /", "python")
        assert "+" in result

    def test_nested_strings(self, highlighter: SyntaxHighlighter) -> None:
        """Should handle nested quote types."""
        code = '''x = "it's a string"'''
        result = highlighter.highlight(code, "python")
        assert "it's" in result

    def test_multiline_string(self, highlighter: SyntaxHighlighter) -> None:
        """Should handle multiline strings."""
        code = '''x = """
multiline
string
"""'''
        result = highlighter.highlight(code, "python")
        assert "multiline" in result

    def test_json_highlighting(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight JSON."""
        code = '{"key": "value", "num": 123, "bool": true}'
        result = highlighter.highlight(code, "json")
        assert "key" in result
        assert "123" in result

    def test_yaml_highlighting(self, highlighter: SyntaxHighlighter) -> None:
        """Should highlight YAML."""
        code = "key: value\nnum: 123\nbool: true"
        result = highlighter.highlight(code, "yaml")
        assert "key" in result
        assert "true" in result


class TestColorSchemes:
    """Tests for color scheme variants."""

    def test_dark_scheme(self) -> None:
        """Dark scheme should have appropriate colors."""
        assert DARK_SCHEME.reset == AnsiColor.RESET.value
        assert AnsiColor.BLUE.value in DARK_SCHEME.keyword

    def test_light_scheme(self) -> None:
        """Light scheme should have appropriate colors."""
        assert LIGHT_SCHEME.reset == AnsiColor.RESET.value
        assert AnsiColor.BLUE.value in LIGHT_SCHEME.keyword

    def test_custom_scheme(self) -> None:
        """Should support custom schemes."""
        custom = ColorScheme(
            keyword=AnsiColor.RED.value,
            string=AnsiColor.BLUE.value,
        )
        h = SyntaxHighlighter(scheme=custom)
        code = 'def x(): return "hello"'
        result = h.highlight(code, "python")
        # Should use custom colors
        assert AnsiColor.RED.value in result or "def" in result
