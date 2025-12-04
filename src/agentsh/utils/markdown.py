"""Markdown rendering for terminal output.

Provides rendering of markdown content to terminal-formatted text
with ANSI colors and formatting.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from agentsh.utils.ux import Color, colorize


class MarkdownStyle(str, Enum):
    """Markdown rendering styles."""

    FULL = "full"  # Full rendering with all features
    SIMPLE = "simple"  # Simplified rendering
    PLAIN = "plain"  # No formatting, just text


@dataclass
class RenderConfig:
    """Configuration for markdown rendering.

    Attributes:
        style: Rendering style
        use_color: Whether to use ANSI colors
        max_width: Maximum line width (0 for unlimited)
        indent_size: Spaces per indentation level
        code_block_style: Style for code blocks
        bullet_char: Character for bullet lists
    """

    style: MarkdownStyle = MarkdownStyle.FULL
    use_color: bool = True
    max_width: int = 80
    indent_size: int = 2
    code_block_style: str = "box"  # "box", "indent", "plain"
    bullet_char: str = "•"


class MarkdownRenderer:
    """Render markdown to terminal-formatted text.

    Supports:
    - Headers (h1-h6)
    - Bold and italic
    - Code (inline and blocks)
    - Lists (ordered and unordered)
    - Links
    - Blockquotes
    - Horizontal rules

    Example:
        renderer = MarkdownRenderer()
        output = renderer.render('''
        # Hello World

        This is **bold** and *italic* text.

        ```python
        print("Hello!")
        ```
        ''')
        print(output)
    """

    # Regex patterns for markdown elements
    PATTERNS = {
        "header": re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE),
        "bold": re.compile(r"\*\*(.+?)\*\*"),
        "italic": re.compile(r"\*(.+?)\*"),
        "bold_alt": re.compile(r"__(.+?)__"),
        "italic_alt": re.compile(r"_(.+?)_"),
        "inline_code": re.compile(r"`([^`]+)`"),
        "code_block": re.compile(r"```(\w*)\n(.*?)```", re.DOTALL),
        "link": re.compile(r"\[([^\]]+)\]\(([^)]+)\)"),
        "image": re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"),
        "blockquote": re.compile(r"^>\s*(.+)$", re.MULTILINE),
        "hr": re.compile(r"^(-{3,}|\*{3,}|_{3,})$", re.MULTILINE),
        "ul_item": re.compile(r"^(\s*)[-*+]\s+(.+)$", re.MULTILINE),
        "ol_item": re.compile(r"^(\s*)(\d+)\.\s+(.+)$", re.MULTILINE),
        "strikethrough": re.compile(r"~~(.+?)~~"),
    }

    def __init__(self, config: Optional[RenderConfig] = None) -> None:
        """Initialize renderer.

        Args:
            config: Rendering configuration
        """
        self.config = config or RenderConfig()

    def render(self, markdown: str) -> str:
        """Render markdown to terminal text.

        Args:
            markdown: Markdown content

        Returns:
            Formatted terminal text
        """
        if self.config.style == MarkdownStyle.PLAIN:
            return self._render_plain(markdown)

        # Process in order to handle nesting
        output = markdown

        # Process code blocks first (to avoid processing markdown inside them)
        output = self._render_code_blocks(output)

        # Process block elements
        output = self._render_headers(output)
        output = self._render_blockquotes(output)
        output = self._render_horizontal_rules(output)
        output = self._render_lists(output)

        # Process inline elements
        output = self._render_inline_code(output)
        output = self._render_bold(output)
        output = self._render_italic(output)
        output = self._render_strikethrough(output)
        output = self._render_images(output)  # Must be before links
        output = self._render_links(output)

        # Restore code blocks from placeholders
        output = self._restore_code_blocks(output)

        # Clean up extra whitespace
        output = self._cleanup(output)

        return output

    def _render_plain(self, markdown: str) -> str:
        """Render markdown as plain text (strip all formatting).

        Args:
            markdown: Markdown content

        Returns:
            Plain text
        """
        output = markdown

        # Remove code blocks, keep content
        output = self.PATTERNS["code_block"].sub(r"\2", output)

        # Remove inline formatting
        output = self.PATTERNS["bold"].sub(r"\1", output)
        output = self.PATTERNS["italic"].sub(r"\1", output)
        output = self.PATTERNS["bold_alt"].sub(r"\1", output)
        output = self.PATTERNS["italic_alt"].sub(r"\1", output)
        output = self.PATTERNS["inline_code"].sub(r"\1", output)
        output = self.PATTERNS["strikethrough"].sub(r"\1", output)

        # Remove headers markers
        output = self.PATTERNS["header"].sub(r"\2", output)

        # Convert links to text
        output = self.PATTERNS["link"].sub(r"\1 (\2)", output)
        output = self.PATTERNS["image"].sub(r"[Image: \1]", output)

        # Remove blockquote markers
        output = self.PATTERNS["blockquote"].sub(r"\1", output)

        # Remove horizontal rules
        output = self.PATTERNS["hr"].sub("", output)

        return output.strip()

    def _render_headers(self, text: str) -> str:
        """Render markdown headers.

        Args:
            text: Input text

        Returns:
            Text with rendered headers
        """

        def replace_header(match: re.Match) -> str:
            level = len(match.group(1))
            content = match.group(2)

            if not self.config.use_color:
                if level == 1:
                    return f"\n{content}\n{'=' * len(content)}\n"
                elif level == 2:
                    return f"\n{content}\n{'─' * len(content)}\n"
                else:
                    return f"\n{'#' * level} {content}\n"

            # Colored headers
            if level == 1:
                header = colorize(content.upper(), Color.BOLD, Color.CYAN)
                underline = colorize("=" * len(content), Color.CYAN)
                return f"\n{header}\n{underline}\n"
            elif level == 2:
                header = colorize(content, Color.BOLD, Color.BLUE)
                underline = colorize("-" * len(content), Color.BLUE)
                return f"\n{header}\n{underline}\n"
            elif level == 3:
                return f"\n{colorize(content, Color.BOLD, Color.GREEN)}\n"
            else:
                return f"\n{colorize(content, Color.BOLD)}\n"

        return self.PATTERNS["header"].sub(replace_header, text)

    def _render_code_blocks(self, text: str) -> str:
        """Render fenced code blocks.

        Args:
            text: Input text

        Returns:
            Text with rendered code blocks
        """
        # Store code blocks to protect them from other processing
        self._code_blocks: list[str] = []

        def replace_code_block(match: re.Match) -> str:
            lang = match.group(1) or ""
            code = match.group(2).strip()

            if self.config.code_block_style == "plain":
                result = f"\n{code}\n"
                self._code_blocks.append(result)
                return f"\x00CODE_BLOCK_{len(self._code_blocks) - 1}\x00"

            lines = code.split("\n")

            if self.config.code_block_style == "indent":
                indented = "\n".join(f"    {line}" for line in lines)
                if self.config.use_color:
                    result = f"\n{colorize(indented, Color.DIM)}\n"
                else:
                    result = f"\n{indented}\n"
                self._code_blocks.append(result)
                return f"\x00CODE_BLOCK_{len(self._code_blocks) - 1}\x00"

            # Box style - preserve content exactly
            max_len = max(len(line) for line in lines) if lines else 0
            width = max(max_len + 4, 40)

            if self.config.use_color:
                top = colorize(f"┌─ {lang} " + "─" * (width - len(lang) - 4) + "┐", Color.DIM)
                bottom = colorize("└" + "─" * (width - 2) + "┘", Color.DIM)
                box_lines = [top]
                for line in lines:
                    padded = line.ljust(width - 4)
                    box_lines.append(colorize("│ ", Color.DIM) + padded + colorize(" │", Color.DIM))
                box_lines.append(bottom)
            else:
                top = f"┌─ {lang} " + "─" * (width - len(lang) - 4) + "┐"
                bottom = "└" + "─" * (width - 2) + "┘"
                box_lines = [top]
                for line in lines:
                    padded = line.ljust(width - 4)
                    box_lines.append(f"│ {padded} │")
                box_lines.append(bottom)

            result = "\n" + "\n".join(box_lines) + "\n"
            self._code_blocks.append(result)
            return f"\x00CODE_BLOCK_{len(self._code_blocks) - 1}\x00"

        return self.PATTERNS["code_block"].sub(replace_code_block, text)

    def _restore_code_blocks(self, text: str) -> str:
        """Restore code blocks from placeholders.

        Args:
            text: Text with placeholders

        Returns:
            Text with code blocks restored
        """
        if not hasattr(self, "_code_blocks"):
            return text

        for i, block in enumerate(self._code_blocks):
            text = text.replace(f"\x00CODE_BLOCK_{i}\x00", block)

        return text

    def _render_inline_code(self, text: str) -> str:
        """Render inline code.

        Args:
            text: Input text

        Returns:
            Text with rendered inline code
        """
        if not self.config.use_color:
            return self.PATTERNS["inline_code"].sub(r"`\1`", text)

        def replace_code(match: re.Match) -> str:
            code = match.group(1)
            return colorize(f"`{code}`", Color.YELLOW)

        return self.PATTERNS["inline_code"].sub(replace_code, text)

    def _render_bold(self, text: str) -> str:
        """Render bold text.

        Args:
            text: Input text

        Returns:
            Text with rendered bold
        """
        if not self.config.use_color:
            text = self.PATTERNS["bold"].sub(r"\1", text)
            text = self.PATTERNS["bold_alt"].sub(r"\1", text)
            return text

        def replace_bold(match: re.Match) -> str:
            content = match.group(1)
            return colorize(content, Color.BOLD)

        text = self.PATTERNS["bold"].sub(replace_bold, text)
        text = self.PATTERNS["bold_alt"].sub(replace_bold, text)
        return text

    def _render_italic(self, text: str) -> str:
        """Render italic text.

        Args:
            text: Input text

        Returns:
            Text with rendered italic
        """
        if not self.config.use_color:
            return self.PATTERNS["italic"].sub(r"\1", text)

        def replace_italic(match: re.Match) -> str:
            content = match.group(1)
            return colorize(content, Color.DIM)

        text = self.PATTERNS["italic"].sub(replace_italic, text)
        text = self.PATTERNS["italic_alt"].sub(replace_italic, text)
        return text

    def _render_strikethrough(self, text: str) -> str:
        """Render strikethrough text.

        Args:
            text: Input text

        Returns:
            Text with rendered strikethrough
        """
        if not self.config.use_color:
            return self.PATTERNS["strikethrough"].sub(r"~\1~", text)

        def replace_strike(match: re.Match) -> str:
            content = match.group(1)
            # Use dim + overstrike effect
            return colorize(content, Color.DIM)

        return self.PATTERNS["strikethrough"].sub(replace_strike, text)

    def _render_links(self, text: str) -> str:
        """Render links.

        Args:
            text: Input text

        Returns:
            Text with rendered links
        """

        def replace_link(match: re.Match) -> str:
            title = match.group(1)
            url = match.group(2)

            if not self.config.use_color:
                return f"{title} ({url})"

            # Render as colored text with URL
            return f"{colorize(title, Color.BLUE, Color.UNDERLINE)} ({colorize(url, Color.DIM)})"

        return self.PATTERNS["link"].sub(replace_link, text)

    def _render_images(self, text: str) -> str:
        """Render image placeholders.

        Args:
            text: Input text

        Returns:
            Text with rendered image placeholders
        """

        def replace_image(match: re.Match) -> str:
            alt = match.group(1) or "image"
            url = match.group(2)

            if not self.config.use_color:
                return f"[Image: {alt}]"

            return colorize(f"[Image: {alt}]", Color.MAGENTA)

        return self.PATTERNS["image"].sub(replace_image, text)

    def _render_blockquotes(self, text: str) -> str:
        """Render blockquotes.

        Args:
            text: Input text

        Returns:
            Text with rendered blockquotes
        """

        def replace_quote(match: re.Match) -> str:
            content = match.group(1)

            if not self.config.use_color:
                return f"  │ {content}"

            return colorize("  │ ", Color.DIM) + colorize(content, Color.DIM)

        return self.PATTERNS["blockquote"].sub(replace_quote, text)

    def _render_horizontal_rules(self, text: str) -> str:
        """Render horizontal rules.

        Args:
            text: Input text

        Returns:
            Text with rendered horizontal rules
        """
        width = self.config.max_width if self.config.max_width > 0 else 40

        if not self.config.use_color:
            rule = "─" * width

        else:
            rule = colorize("─" * width, Color.DIM)

        return self.PATTERNS["hr"].sub(f"\n{rule}\n", text)

    def _render_lists(self, text: str) -> str:
        """Render ordered and unordered lists.

        Args:
            text: Input text

        Returns:
            Text with rendered lists
        """
        bullet = self.config.bullet_char

        def replace_ul(match: re.Match) -> str:
            indent = match.group(1)
            content = match.group(2)
            level = len(indent) // 2

            if not self.config.use_color:
                return f"{indent}{bullet} {content}"

            bullet_colored = colorize(bullet, Color.CYAN)
            return f"{indent}{bullet_colored} {content}"

        def replace_ol(match: re.Match) -> str:
            indent = match.group(1)
            number = match.group(2)
            content = match.group(3)

            if not self.config.use_color:
                return f"{indent}{number}. {content}"

            num_colored = colorize(f"{number}.", Color.CYAN)
            return f"{indent}{num_colored} {content}"

        text = self.PATTERNS["ul_item"].sub(replace_ul, text)
        text = self.PATTERNS["ol_item"].sub(replace_ol, text)
        return text

    def _cleanup(self, text: str) -> str:
        """Clean up extra whitespace.

        Args:
            text: Input text

        Returns:
            Cleaned text
        """
        # Remove excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Strip leading/trailing newlines
        text = text.strip("\n")

        # If result is only whitespace, return empty string
        if not text.strip():
            return ""

        return text


# Global renderer instance
_renderer: Optional[MarkdownRenderer] = None


def get_markdown_renderer() -> MarkdownRenderer:
    """Get the global markdown renderer.

    Returns:
        MarkdownRenderer instance
    """
    global _renderer
    if _renderer is None:
        _renderer = MarkdownRenderer()
    return _renderer


def render_markdown(
    markdown: str,
    use_color: bool = True,
    style: MarkdownStyle = MarkdownStyle.FULL,
) -> str:
    """Convenience function to render markdown.

    Args:
        markdown: Markdown content
        use_color: Whether to use ANSI colors
        style: Rendering style

    Returns:
        Formatted terminal text
    """
    config = RenderConfig(use_color=use_color, style=style)
    renderer = MarkdownRenderer(config)
    return renderer.render(markdown)


def strip_markdown(markdown: str) -> str:
    """Strip all markdown formatting, leaving plain text.

    Args:
        markdown: Markdown content

    Returns:
        Plain text without formatting
    """
    return render_markdown(markdown, style=MarkdownStyle.PLAIN)
