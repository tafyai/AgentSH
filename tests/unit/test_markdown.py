"""Tests for markdown rendering module."""

import pytest

from agentsh.utils.markdown import (
    MarkdownRenderer,
    MarkdownStyle,
    RenderConfig,
    get_markdown_renderer,
    render_markdown,
    strip_markdown,
)
from agentsh.utils.ux import Color


class TestRenderConfig:
    """Tests for RenderConfig dataclass."""

    def test_default_config(self) -> None:
        """Should have sensible defaults."""
        config = RenderConfig()
        assert config.style == MarkdownStyle.FULL
        assert config.use_color is True
        assert config.max_width == 80
        assert config.bullet_char == "•"

    def test_custom_config(self) -> None:
        """Should accept custom values."""
        config = RenderConfig(
            style=MarkdownStyle.SIMPLE,
            use_color=False,
            max_width=120,
        )
        assert config.style == MarkdownStyle.SIMPLE
        assert config.use_color is False
        assert config.max_width == 120


class TestMarkdownRenderer:
    """Tests for MarkdownRenderer class."""

    @pytest.fixture
    def renderer(self) -> MarkdownRenderer:
        """Create renderer with colors disabled for testing."""
        config = RenderConfig(use_color=False)
        return MarkdownRenderer(config)

    @pytest.fixture
    def color_renderer(self) -> MarkdownRenderer:
        """Create renderer with colors enabled."""
        config = RenderConfig(use_color=True)
        return MarkdownRenderer(config)

    # Header tests

    def test_render_h1(self, renderer: MarkdownRenderer) -> None:
        """Should render h1 headers."""
        output = renderer.render("# Hello World")
        assert "Hello World" in output
        assert "=" in output  # Underline

    def test_render_h2(self, renderer: MarkdownRenderer) -> None:
        """Should render h2 headers."""
        output = renderer.render("## Section Title")
        assert "Section Title" in output
        assert "─" in output  # Underline (box-drawing character)

    def test_render_h3(self, renderer: MarkdownRenderer) -> None:
        """Should render h3 headers."""
        output = renderer.render("### Subsection")
        assert "Subsection" in output

    def test_render_h1_colored(self, color_renderer: MarkdownRenderer) -> None:
        """Should render colored h1."""
        output = color_renderer.render("# Colored Header")
        assert "Colored Header".upper() in output
        assert Color.CYAN.value in output

    # Bold and italic tests

    def test_render_bold(self, renderer: MarkdownRenderer) -> None:
        """Should render bold text."""
        output = renderer.render("This is **bold** text.")
        assert "bold" in output
        assert "**" not in output

    def test_render_italic(self, renderer: MarkdownRenderer) -> None:
        """Should render italic text."""
        output = renderer.render("This is *italic* text.")
        assert "italic" in output
        assert output.count("*") == 0 or "*italic*" not in output

    def test_render_bold_alt(self, renderer: MarkdownRenderer) -> None:
        """Should render bold with underscore syntax."""
        output = renderer.render("This is __bold__ text.")
        assert "bold" in output
        assert "__" not in output

    def test_render_bold_colored(self, color_renderer: MarkdownRenderer) -> None:
        """Should render colored bold."""
        output = color_renderer.render("This is **bold** text.")
        assert Color.BOLD.value in output

    # Code tests

    def test_render_inline_code(self, renderer: MarkdownRenderer) -> None:
        """Should render inline code."""
        output = renderer.render("Use `print()` function.")
        assert "print()" in output

    def test_render_inline_code_colored(self, color_renderer: MarkdownRenderer) -> None:
        """Should render colored inline code."""
        output = color_renderer.render("Use `code` here.")
        assert Color.YELLOW.value in output

    def test_render_code_block(self, renderer: MarkdownRenderer) -> None:
        """Should render code blocks."""
        md = """```python
def hello():
    print("Hello")
```"""
        output = renderer.render(md)
        assert "def hello():" in output
        assert "print" in output

    def test_render_code_block_box_style(self, renderer: MarkdownRenderer) -> None:
        """Should render code block with box."""
        md = """```
code here
```"""
        output = renderer.render(md)
        assert "┌" in output  # Box character
        assert "┘" in output

    def test_render_code_block_indent_style(self) -> None:
        """Should render code block with indent style."""
        config = RenderConfig(use_color=False, code_block_style="indent")
        renderer = MarkdownRenderer(config)

        md = """```
code here
```"""
        output = renderer.render(md)
        assert "    code here" in output

    # Link tests

    def test_render_link(self, renderer: MarkdownRenderer) -> None:
        """Should render links."""
        output = renderer.render("[Click here](https://example.com)")
        assert "Click here" in output
        assert "https://example.com" in output

    def test_render_link_colored(self, color_renderer: MarkdownRenderer) -> None:
        """Should render colored links."""
        output = color_renderer.render("[Link](https://test.com)")
        assert Color.BLUE.value in output

    # Image tests

    def test_render_image(self, renderer: MarkdownRenderer) -> None:
        """Should render image placeholder."""
        output = renderer.render("![Alt text](image.png)")
        assert "Image:" in output
        assert "Alt text" in output

    # Blockquote tests

    def test_render_blockquote(self, renderer: MarkdownRenderer) -> None:
        """Should render blockquotes."""
        output = renderer.render("> This is a quote")
        assert "This is a quote" in output
        assert "│" in output

    def test_render_multiline_blockquote(self, renderer: MarkdownRenderer) -> None:
        """Should render multiline blockquotes."""
        md = """> Line one
> Line two"""
        output = renderer.render(md)
        assert "Line one" in output
        assert "Line two" in output

    # List tests

    def test_render_unordered_list(self, renderer: MarkdownRenderer) -> None:
        """Should render unordered lists."""
        md = """- Item 1
- Item 2
- Item 3"""
        output = renderer.render(md)
        assert "Item 1" in output
        assert "Item 2" in output
        assert "•" in output  # Bullet character

    def test_render_ordered_list(self, renderer: MarkdownRenderer) -> None:
        """Should render ordered lists."""
        md = """1. First
2. Second
3. Third"""
        output = renderer.render(md)
        assert "First" in output
        assert "Second" in output
        assert "1." in output

    def test_render_nested_list(self, renderer: MarkdownRenderer) -> None:
        """Should render nested lists."""
        md = """- Parent
  - Child 1
  - Child 2"""
        output = renderer.render(md)
        assert "Parent" in output
        assert "Child 1" in output

    # Horizontal rule tests

    def test_render_horizontal_rule(self, renderer: MarkdownRenderer) -> None:
        """Should render horizontal rules."""
        output = renderer.render("---")
        assert "─" in output

    def test_render_hr_variants(self, renderer: MarkdownRenderer) -> None:
        """Should handle different HR syntaxes."""
        for hr in ["---", "***", "___"]:
            output = renderer.render(hr)
            assert "─" in output

    # Strikethrough tests

    def test_render_strikethrough(self, renderer: MarkdownRenderer) -> None:
        """Should render strikethrough."""
        output = renderer.render("This is ~~deleted~~ text.")
        assert "deleted" in output
        assert "~~" not in output

    # Combined elements

    def test_render_complex_document(self, renderer: MarkdownRenderer) -> None:
        """Should render complex markdown documents."""
        md = """# Title

This is a paragraph with **bold** and *italic*.

## Section 1

- Item 1
- Item 2

```python
print("code")
```

> A quote

---

[Link](https://example.com)
"""
        output = renderer.render(md)

        # Check all elements present
        assert "Title" in output
        assert "bold" in output
        assert "italic" in output
        assert "Section 1" in output
        assert "Item 1" in output
        assert "print" in output
        assert "A quote" in output
        assert "Link" in output
        assert "example.com" in output

    # Plain style tests

    def test_render_plain_style(self) -> None:
        """Should strip all formatting in plain mode."""
        config = RenderConfig(style=MarkdownStyle.PLAIN)
        renderer = MarkdownRenderer(config)

        md = "# Header\n\n**bold** and *italic*\n\n`code`"
        output = renderer.render(md)

        # No markdown syntax
        assert "#" not in output
        assert "**" not in output
        assert "*italic*" not in output
        assert "`" not in output

        # Content preserved
        assert "Header" in output
        assert "bold" in output
        assert "italic" in output
        assert "code" in output


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_render_markdown(self) -> None:
        """Should render markdown via convenience function."""
        output = render_markdown("# Hello", use_color=False)
        assert "Hello" in output
        assert "=" in output

    def test_render_markdown_no_color(self) -> None:
        """Should render without color."""
        output = render_markdown("**bold**", use_color=False)
        assert Color.BOLD.value not in output
        assert "bold" in output

    def test_render_markdown_with_color(self) -> None:
        """Should render with color."""
        output = render_markdown("**bold**", use_color=True)
        assert Color.BOLD.value in output

    def test_strip_markdown(self) -> None:
        """Should strip markdown formatting."""
        output = strip_markdown("# Header\n\n**bold** text")
        assert "Header" in output
        assert "bold" in output
        assert "#" not in output
        assert "**" not in output

    def test_get_markdown_renderer_singleton(self) -> None:
        """Should return same instance."""
        r1 = get_markdown_renderer()
        r2 = get_markdown_renderer()
        assert r1 is r2


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_input(self) -> None:
        """Should handle empty input."""
        renderer = MarkdownRenderer()
        output = renderer.render("")
        assert output == ""

    def test_whitespace_only(self) -> None:
        """Should handle whitespace-only input."""
        renderer = MarkdownRenderer()
        output = renderer.render("   \n\n   ")
        assert output == ""

    def test_no_markdown(self) -> None:
        """Should handle plain text."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        output = renderer.render("Plain text without markdown.")
        assert output == "Plain text without markdown."

    def test_unclosed_formatting(self) -> None:
        """Should handle unclosed formatting gracefully."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        # Unclosed bold - should not crash
        output = renderer.render("This is **unclosed bold")
        assert "unclosed bold" in output

    def test_nested_formatting(self) -> None:
        """Should handle nested formatting."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        output = renderer.render("***bold and italic***")
        assert "bold and italic" in output

    def test_code_block_preserves_content(self) -> None:
        """Should preserve content inside code blocks."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        md = """```
**not bold**
# not header
```"""
        output = renderer.render(md)
        # These should be preserved as-is inside code block
        assert "**not bold**" in output
        assert "# not header" in output

    def test_special_characters(self) -> None:
        """Should handle special characters."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        output = renderer.render("Special chars: < > & \" '")
        assert "< > & \" '" in output

    def test_unicode(self) -> None:
        """Should handle unicode content."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        output = renderer.render("# 你好世界\n\nÉmoji: 🎉")
        assert "你好世界" in output
        assert "🎉" in output
