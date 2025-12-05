"""Syntax highlighting for code output.

Provides terminal-based syntax highlighting for various programming languages
using ANSI escape codes. Works without external dependencies.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class TokenType(str, Enum):
    """Types of syntax tokens."""

    KEYWORD = "keyword"
    STRING = "string"
    NUMBER = "number"
    COMMENT = "comment"
    OPERATOR = "operator"
    FUNCTION = "function"
    CLASS = "class"
    DECORATOR = "decorator"
    BUILTIN = "builtin"
    VARIABLE = "variable"
    CONSTANT = "constant"
    TYPE = "type"
    PUNCTUATION = "punctuation"
    DEFAULT = "default"


class AnsiColor(str, Enum):
    """ANSI color codes for syntax highlighting."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


@dataclass
class ColorScheme:
    """Color scheme for syntax highlighting."""

    keyword: str = AnsiColor.BLUE.value + AnsiColor.BOLD.value
    string: str = AnsiColor.GREEN.value
    number: str = AnsiColor.CYAN.value
    comment: str = AnsiColor.BRIGHT_BLACK.value + AnsiColor.ITALIC.value
    operator: str = AnsiColor.YELLOW.value
    function: str = AnsiColor.BRIGHT_BLUE.value
    class_name: str = AnsiColor.BRIGHT_CYAN.value + AnsiColor.BOLD.value
    decorator: str = AnsiColor.MAGENTA.value
    builtin: str = AnsiColor.CYAN.value
    variable: str = AnsiColor.WHITE.value
    constant: str = AnsiColor.BRIGHT_MAGENTA.value
    type_hint: str = AnsiColor.BRIGHT_CYAN.value
    punctuation: str = AnsiColor.WHITE.value
    default: str = AnsiColor.WHITE.value
    reset: str = AnsiColor.RESET.value

    def get_color(self, token_type: TokenType) -> str:
        """Get color for a token type."""
        mapping = {
            TokenType.KEYWORD: self.keyword,
            TokenType.STRING: self.string,
            TokenType.NUMBER: self.number,
            TokenType.COMMENT: self.comment,
            TokenType.OPERATOR: self.operator,
            TokenType.FUNCTION: self.function,
            TokenType.CLASS: self.class_name,
            TokenType.DECORATOR: self.decorator,
            TokenType.BUILTIN: self.builtin,
            TokenType.VARIABLE: self.variable,
            TokenType.CONSTANT: self.constant,
            TokenType.TYPE: self.type_hint,
            TokenType.PUNCTUATION: self.punctuation,
            TokenType.DEFAULT: self.default,
        }
        return mapping.get(token_type, self.default)


# Default color schemes
DARK_SCHEME = ColorScheme()

LIGHT_SCHEME = ColorScheme(
    keyword=AnsiColor.BLUE.value + AnsiColor.BOLD.value,
    string=AnsiColor.RED.value,
    number=AnsiColor.MAGENTA.value,
    comment=AnsiColor.BRIGHT_BLACK.value,
    operator=AnsiColor.BLACK.value,
    function=AnsiColor.BLUE.value,
    class_name=AnsiColor.CYAN.value + AnsiColor.BOLD.value,
    decorator=AnsiColor.MAGENTA.value,
    builtin=AnsiColor.CYAN.value,
    variable=AnsiColor.BLACK.value,
    constant=AnsiColor.MAGENTA.value,
    type_hint=AnsiColor.CYAN.value,
    punctuation=AnsiColor.BLACK.value,
    default=AnsiColor.BLACK.value,
)


@dataclass
class LanguageDefinition:
    """Definition for a programming language's syntax."""

    name: str
    keywords: set[str] = field(default_factory=set)
    builtins: set[str] = field(default_factory=set)
    constants: set[str] = field(default_factory=set)
    types: set[str] = field(default_factory=set)
    operators: str = r"[+\-*/%=<>!&|^~]+"
    string_delimiters: list[str] = field(default_factory=lambda: ['"', "'"])
    comment_single: str = "#"
    comment_multi_start: Optional[str] = None
    comment_multi_end: Optional[str] = None
    decorator_prefix: Optional[str] = "@"


# Language definitions
PYTHON = LanguageDefinition(
    name="python",
    keywords={
        "and", "as", "assert", "async", "await", "break", "class", "continue",
        "def", "del", "elif", "else", "except", "finally", "for", "from",
        "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
        "or", "pass", "raise", "return", "try", "while", "with", "yield",
        "match", "case",
    },
    builtins={
        "abs", "all", "any", "bin", "bool", "bytes", "callable", "chr",
        "classmethod", "compile", "complex", "delattr", "dict", "dir",
        "divmod", "enumerate", "eval", "exec", "filter", "float", "format",
        "frozenset", "getattr", "globals", "hasattr", "hash", "help", "hex",
        "id", "input", "int", "isinstance", "issubclass", "iter", "len",
        "list", "locals", "map", "max", "memoryview", "min", "next", "object",
        "oct", "open", "ord", "pow", "print", "property", "range", "repr",
        "reversed", "round", "set", "setattr", "slice", "sorted", "staticmethod",
        "str", "sum", "super", "tuple", "type", "vars", "zip",
    },
    constants={"True", "False", "None", "Ellipsis", "NotImplemented"},
    types={"int", "str", "float", "bool", "list", "dict", "set", "tuple", "Optional", "Any", "Union"},
    comment_single="#",
    comment_multi_start='"""',
    comment_multi_end='"""',
    decorator_prefix="@",
)

JAVASCRIPT = LanguageDefinition(
    name="javascript",
    keywords={
        "async", "await", "break", "case", "catch", "class", "const",
        "continue", "debugger", "default", "delete", "do", "else", "export",
        "extends", "finally", "for", "function", "if", "import", "in",
        "instanceof", "let", "new", "return", "super", "switch", "this",
        "throw", "try", "typeof", "var", "void", "while", "with", "yield",
        "static", "get", "set",
    },
    builtins={
        "console", "window", "document", "Array", "Object", "String", "Number",
        "Boolean", "Function", "Symbol", "Map", "Set", "WeakMap", "WeakSet",
        "Promise", "Proxy", "Reflect", "JSON", "Math", "Date", "RegExp",
        "Error", "parseInt", "parseFloat", "isNaN", "isFinite", "setTimeout",
        "setInterval", "clearTimeout", "clearInterval", "fetch", "require",
    },
    constants={"true", "false", "null", "undefined", "NaN", "Infinity"},
    types={"string", "number", "boolean", "object", "any", "void", "never"},
    comment_single="//",
    comment_multi_start="/*",
    comment_multi_end="*/",
    decorator_prefix="@",
)

BASH = LanguageDefinition(
    name="bash",
    keywords={
        "if", "then", "else", "elif", "fi", "case", "esac", "for", "while",
        "until", "do", "done", "in", "function", "select", "time", "coproc",
        "local", "return", "exit", "break", "continue", "declare", "typeset",
        "readonly", "export", "unset", "shift", "source", "alias", "unalias",
    },
    builtins={
        "echo", "printf", "read", "cd", "pwd", "pushd", "popd", "dirs", "let",
        "eval", "set", "test", "true", "false", "command", "builtin", "type",
        "hash", "bind", "help", "logout", "mapfile", "readarray", "exec",
        "trap", "wait", "kill", "jobs", "fg", "bg", "disown", "suspend",
        "ls", "cat", "grep", "sed", "awk", "find", "xargs", "sort", "uniq",
        "wc", "head", "tail", "cut", "tr", "tee", "diff", "patch", "tar",
        "gzip", "gunzip", "zip", "unzip", "curl", "wget", "ssh", "scp",
        "git", "docker", "kubectl", "make", "npm", "pip", "python", "node",
    },
    constants=set(),
    types=set(),
    string_delimiters=['"', "'", "`"],
    comment_single="#",
    decorator_prefix=None,
)

JSON_LANG = LanguageDefinition(
    name="json",
    keywords=set(),
    builtins=set(),
    constants={"true", "false", "null"},
    types=set(),
    string_delimiters=['"'],
    comment_single="",
    decorator_prefix=None,
)

YAML_LANG = LanguageDefinition(
    name="yaml",
    keywords=set(),
    builtins=set(),
    constants={"true", "false", "null", "yes", "no", "on", "off"},
    types=set(),
    string_delimiters=['"', "'"],
    comment_single="#",
    decorator_prefix=None,
)

# Language mapping
LANGUAGES: dict[str, LanguageDefinition] = {
    "python": PYTHON,
    "py": PYTHON,
    "javascript": JAVASCRIPT,
    "js": JAVASCRIPT,
    "typescript": JAVASCRIPT,
    "ts": JAVASCRIPT,
    "bash": BASH,
    "sh": BASH,
    "shell": BASH,
    "zsh": BASH,
    "json": JSON_LANG,
    "yaml": YAML_LANG,
    "yml": YAML_LANG,
}


class SyntaxHighlighter:
    """Syntax highlighter for code.

    Highlights code using ANSI escape codes based on language-specific
    patterns and rules.

    Example:
        highlighter = SyntaxHighlighter()
        highlighted = highlighter.highlight(code, "python")
        print(highlighted)
    """

    def __init__(
        self,
        scheme: Optional[ColorScheme] = None,
        use_color: bool = True,
    ) -> None:
        """Initialize the highlighter.

        Args:
            scheme: Color scheme to use
            use_color: Whether to apply colors
        """
        self.scheme = scheme or DARK_SCHEME
        self.use_color = use_color

    def highlight(self, code: str, language: str = "python") -> str:
        """Highlight code with syntax colors.

        Args:
            code: Source code to highlight
            language: Programming language

        Returns:
            Highlighted code with ANSI escape codes
        """
        if not self.use_color:
            return code

        lang_def = LANGUAGES.get(language.lower())
        if not lang_def:
            return code

        return self._highlight_with_language(code, lang_def)

    def _highlight_with_language(
        self, code: str, lang: LanguageDefinition
    ) -> str:
        """Highlight code using language definition.

        Args:
            code: Source code
            lang: Language definition

        Returns:
            Highlighted code
        """
        lines = code.split("\n")
        highlighted_lines = []
        in_multiline_string = False
        in_multiline_comment = False

        for line in lines:
            if in_multiline_comment:
                # Check for end of multiline comment
                if lang.comment_multi_end and lang.comment_multi_end in line:
                    end_idx = line.index(lang.comment_multi_end) + len(lang.comment_multi_end)
                    comment_part = line[:end_idx]
                    rest = line[end_idx:]
                    highlighted = (
                        self._colorize(comment_part, TokenType.COMMENT)
                        + self._highlight_line(rest, lang)
                    )
                    in_multiline_comment = False
                else:
                    highlighted = self._colorize(line, TokenType.COMMENT)
            elif in_multiline_string:
                # Check for end of multiline string
                if '"""' in line or "'''" in line:
                    highlighted = self._colorize(line, TokenType.STRING)
                    in_multiline_string = False
                else:
                    highlighted = self._colorize(line, TokenType.STRING)
            else:
                # Check for start of multiline comment
                if lang.comment_multi_start and lang.comment_multi_start in line:
                    if lang.comment_multi_end not in line[line.index(lang.comment_multi_start) + len(lang.comment_multi_start):]:
                        start_idx = line.index(lang.comment_multi_start)
                        before = self._highlight_line(line[:start_idx], lang)
                        after = self._colorize(line[start_idx:], TokenType.COMMENT)
                        highlighted = before + after
                        in_multiline_comment = True
                    else:
                        highlighted = self._highlight_line(line, lang)
                # Check for multiline string
                elif '"""' in line or "'''" in line:
                    # Simple check - if odd number of triple quotes, we're entering/exiting
                    triple_double = line.count('"""')
                    triple_single = line.count("'''")
                    if (triple_double % 2 == 1) or (triple_single % 2 == 1):
                        highlighted = self._colorize(line, TokenType.STRING)
                        in_multiline_string = True
                    else:
                        highlighted = self._highlight_line(line, lang)
                else:
                    highlighted = self._highlight_line(line, lang)

            highlighted_lines.append(highlighted)

        return "\n".join(highlighted_lines)

    def _highlight_line(self, line: str, lang: LanguageDefinition) -> str:
        """Highlight a single line of code.

        Args:
            line: Line of code
            lang: Language definition

        Returns:
            Highlighted line
        """
        if not line.strip():
            return line

        # Handle single-line comments
        if lang.comment_single and lang.comment_single in line:
            comment_idx = self._find_comment_start(line, lang)
            if comment_idx >= 0:
                before = self._highlight_tokens(line[:comment_idx], lang)
                comment = self._colorize(line[comment_idx:], TokenType.COMMENT)
                return before + comment

        return self._highlight_tokens(line, lang)

    def _find_comment_start(self, line: str, lang: LanguageDefinition) -> int:
        """Find where a comment starts, accounting for strings.

        Args:
            line: Line of code
            lang: Language definition

        Returns:
            Index of comment start, or -1 if none
        """
        in_string = False
        string_char = None
        i = 0

        while i < len(line):
            char = line[i]

            # Check for string delimiters
            if char in lang.string_delimiters and (i == 0 or line[i-1] != "\\"):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None

            # Check for comment
            if not in_string and line[i:].startswith(lang.comment_single):
                return i

            i += 1

        return -1

    def _highlight_tokens(self, text: str, lang: LanguageDefinition) -> str:
        """Highlight tokens in text.

        Args:
            text: Text to highlight
            lang: Language definition

        Returns:
            Highlighted text
        """
        result = []
        i = 0

        while i < len(text):
            # Check for decorator
            if lang.decorator_prefix and text[i:].startswith(lang.decorator_prefix):
                # Find end of decorator
                end = i + 1
                while end < len(text) and (text[end].isalnum() or text[end] in "_."):
                    end += 1
                result.append(self._colorize(text[i:end], TokenType.DECORATOR))
                i = end
                continue

            # Check for strings
            for delim in lang.string_delimiters:
                if text[i:].startswith(delim):
                    end = self._find_string_end(text, i, delim)
                    result.append(self._colorize(text[i:end], TokenType.STRING))
                    i = end
                    break
            else:
                # Check for numbers
                if text[i].isdigit() or (text[i] == "." and i + 1 < len(text) and text[i + 1].isdigit()):
                    end = i
                    while end < len(text) and (text[end].isdigit() or text[end] in ".xXeEabcdefABCDEF_"):
                        end += 1
                    result.append(self._colorize(text[i:end], TokenType.NUMBER))
                    i = end
                    continue

                # Check for words (keywords, builtins, etc.)
                if text[i].isalpha() or text[i] == "_":
                    end = i
                    while end < len(text) and (text[end].isalnum() or text[end] == "_"):
                        end += 1
                    word = text[i:end]

                    # Determine token type
                    if word in lang.keywords:
                        token_type = TokenType.KEYWORD
                    elif word in lang.constants:
                        token_type = TokenType.CONSTANT
                    elif word in lang.builtins:
                        token_type = TokenType.BUILTIN
                    elif word in lang.types:
                        token_type = TokenType.TYPE
                    elif end < len(text) and text[end] == "(":
                        token_type = TokenType.FUNCTION
                    elif word[0].isupper():
                        token_type = TokenType.CLASS
                    else:
                        token_type = TokenType.DEFAULT

                    result.append(self._colorize(word, token_type))
                    i = end
                    continue

                # Check for operators
                if re.match(lang.operators, text[i:]):
                    match = re.match(lang.operators, text[i:])
                    if match:
                        op = match.group()
                        result.append(self._colorize(op, TokenType.OPERATOR))
                        i += len(op)
                        continue

                # Default: append character as-is
                result.append(text[i])
                i += 1

        return "".join(result)

    def _find_string_end(self, text: str, start: int, delim: str) -> int:
        """Find the end of a string.

        Args:
            text: Full text
            start: Start index of string
            delim: String delimiter

        Returns:
            Index after string end
        """
        i = start + len(delim)
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text):
                i += 2  # Skip escaped character
                continue
            if text[i:].startswith(delim):
                return i + len(delim)
            i += 1
        return len(text)

    def _colorize(self, text: str, token_type: TokenType) -> str:
        """Apply color to text.

        Args:
            text: Text to colorize
            token_type: Type of token

        Returns:
            Colorized text
        """
        if not self.use_color or not text:
            return text
        color = self.scheme.get_color(token_type)
        return f"{color}{text}{self.scheme.reset}"


# Global highlighter instance
_highlighter: Optional[SyntaxHighlighter] = None


def get_highlighter(
    scheme: Optional[ColorScheme] = None,
    use_color: bool = True,
) -> SyntaxHighlighter:
    """Get or create the global syntax highlighter.

    Args:
        scheme: Color scheme (only used on first call)
        use_color: Whether to use colors

    Returns:
        Global SyntaxHighlighter instance
    """
    global _highlighter
    if _highlighter is None:
        _highlighter = SyntaxHighlighter(scheme=scheme, use_color=use_color)
    return _highlighter


def highlight(code: str, language: str = "python") -> str:
    """Highlight code using the global highlighter.

    Args:
        code: Source code
        language: Programming language

    Returns:
        Highlighted code
    """
    return get_highlighter().highlight(code, language)


def highlight_file(filepath: str, language: Optional[str] = None) -> str:
    """Highlight code from a file.

    Args:
        filepath: Path to source file
        language: Language (auto-detected from extension if None)

    Returns:
        Highlighted code
    """
    # Auto-detect language from extension
    if language is None:
        ext = filepath.rsplit(".", 1)[-1] if "." in filepath else ""
        language = ext

    with open(filepath, "r") as f:
        code = f.read()

    return highlight(code, language)
