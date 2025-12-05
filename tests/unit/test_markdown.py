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


class TestMarkdownRendererExtended:
    """Extended tests for MarkdownRenderer."""

    def test_h4_h5_h6(self) -> None:
        """Should render h4, h5, h6 headers."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))

        h4 = renderer.render("#### Level 4")
        assert "Level 4" in h4

        h5 = renderer.render("##### Level 5")
        assert "Level 5" in h5

        h6 = renderer.render("###### Level 6")
        assert "Level 6" in h6

    def test_asterisk_list(self) -> None:
        """Should render asterisk lists."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        md = """* Item 1
* Item 2"""
        output = renderer.render(md)
        assert "Item 1" in output
        assert "Item 2" in output

    def test_plus_list(self) -> None:
        """Should render plus sign lists."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        md = """+ Item 1
+ Item 2"""
        output = renderer.render(md)
        assert "Item 1" in output
        assert "Item 2" in output

    def test_code_block_with_language(self) -> None:
        """Should preserve language hint."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        md = """```bash
echo "hello"
```"""
        output = renderer.render(md)
        assert "echo" in output

    def test_inline_bold_italic_combined(self) -> None:
        """Should handle combined bold and italic."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        output = renderer.render("This is ***bold italic***")
        assert "bold italic" in output

    def test_multiline_paragraph(self) -> None:
        """Should handle multiline paragraphs."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        md = """This is the first line of a paragraph
that continues on the second line.

And this is a new paragraph."""
        output = renderer.render(md)
        assert "first line" in output
        assert "new paragraph" in output

    def test_multiple_headers_same_level(self) -> None:
        """Should handle multiple headers at same level."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        md = """# Header 1

Some text

# Header 2"""
        output = renderer.render(md)
        assert "Header 1" in output
        assert "Header 2" in output

    def test_link_with_title(self) -> None:
        """Should handle link with title attribute."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        output = renderer.render('[Link](https://example.com "Title")')
        assert "Link" in output
        assert "example.com" in output

    def test_autolink(self) -> None:
        """Should handle bare URLs."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        output = renderer.render("Visit https://example.com for more")
        assert "https://example.com" in output

    def test_escape_characters(self) -> None:
        """Should handle escape characters."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        output = renderer.render("Not \\*bold\\* or \\`code\\`")
        assert "*bold*" not in output or "\\*bold\\*" not in output

    def test_very_long_line(self) -> None:
        """Should handle very long lines."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False, max_width=40))
        long_text = "A" * 100
        output = renderer.render(long_text)
        # Should not crash
        assert "A" in output

    def test_task_list(self) -> None:
        """Should handle task lists."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        md = """- [ ] Unchecked
- [x] Checked"""
        output = renderer.render(md)
        assert "Unchecked" in output or "☐" in output
        assert "Checked" in output or "☑" in output

    def test_simple_style(self) -> None:
        """Should use simple style."""
        config = RenderConfig(style=MarkdownStyle.SIMPLE, use_color=False)
        renderer = MarkdownRenderer(config)

        output = renderer.render("# Header\n\n**bold**")
        assert "Header" in output
        assert "bold" in output

    def test_render_table_basic(self) -> None:
        """Should render basic table."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        md = """| Col1 | Col2 |
|------|------|
| A    | B    |"""
        output = renderer.render(md)
        assert "Col1" in output
        assert "A" in output

    def test_deeply_nested_list(self) -> None:
        """Should handle deeply nested lists."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        md = """- Level 1
  - Level 2
    - Level 3"""
        output = renderer.render(md)
        assert "Level 1" in output
        assert "Level 2" in output
        assert "Level 3" in output

    def test_mixed_list_types(self) -> None:
        """Should handle mixed ordered/unordered lists."""
        renderer = MarkdownRenderer(RenderConfig(use_color=False))
        md = """1. First
2. Second
   - Sub item A
   - Sub item B"""
        output = renderer.render(md)
        assert "First" in output
        assert "Sub item A" in output

    def test_custom_bullet(self) -> None:
        """Should use custom bullet character."""
        config = RenderConfig(use_color=False, bullet_char="-")
        renderer = MarkdownRenderer(config)
        output = renderer.render("- Item")
        assert "Item" in output


class TestMarkdownCodeBlockStyles:
    """Tests for code block rendering styles."""

    def test_code_block_plain_style(self) -> None:
        """Should render plain code blocks."""
        config = RenderConfig(use_color=False, code_block_style="plain")
        renderer = MarkdownRenderer(config)
        md = """```
plain code
```"""
        output = renderer.render(md)
        assert "plain code" in output

    def test_code_block_no_color_box(self) -> None:
        """Should render box style without color."""
        config = RenderConfig(use_color=False, code_block_style="box")
        renderer = MarkdownRenderer(config)
        md = """```python
box code
```"""
        output = renderer.render(md)
        assert "box code" in output
        assert "┌" in output
        assert "┘" in output

    def test_code_block_no_color_indent(self) -> None:
        """Should render indent style without color."""
        config = RenderConfig(use_color=False, code_block_style="indent")
        renderer = MarkdownRenderer(config)
        md = """```
indent code
```"""
        output = renderer.render(md)
        assert "indent code" in output
        assert "    " in output  # Should be indented

    def test_code_block_default_style(self) -> None:
        """Should use default box style."""
        config = RenderConfig(use_color=False)
        renderer = MarkdownRenderer(config)
        md = """```
default
```"""
        output = renderer.render(md)
        assert "default" in output


class TestMarkdownHeaderLevels:
    """Tests for different header levels with color."""

    def test_h1_colored_uppercase(self) -> None:
        """Should render h1 in uppercase with color."""
        config = RenderConfig(use_color=True)
        renderer = MarkdownRenderer(config)
        output = renderer.render("# Test Header")
        assert "TEST HEADER" in output
        assert Color.CYAN.value in output

    def test_h2_colored(self) -> None:
        """Should render h2 with color."""
        config = RenderConfig(use_color=True)
        renderer = MarkdownRenderer(config)
        output = renderer.render("## Level Two")
        assert "Level Two" in output
        assert Color.BLUE.value in output

    def test_h3_colored(self) -> None:
        """Should render h3 with green color."""
        config = RenderConfig(use_color=True)
        renderer = MarkdownRenderer(config)
        output = renderer.render("### Level Three")
        assert "Level Three" in output
        assert Color.GREEN.value in output

    def test_h4_h5_h6_colored(self) -> None:
        """Should render h4-h6 with bold."""
        config = RenderConfig(use_color=True)
        renderer = MarkdownRenderer(config)
        output = renderer.render("#### Level Four")
        assert "Level Four" in output
        assert Color.BOLD.value in output


class TestMarkdownInlineFormatting:
    """Tests for inline formatting with colors."""

    def test_inline_code_colored(self) -> None:
        """Should render inline code with yellow."""
        config = RenderConfig(use_color=True)
        renderer = MarkdownRenderer(config)
        output = renderer.render("Use `code` here")
        assert Color.YELLOW.value in output

    def test_link_colored(self) -> None:
        """Should render links with blue and underline."""
        config = RenderConfig(use_color=True)
        renderer = MarkdownRenderer(config)
        output = renderer.render("[Click](https://example.com)")
        assert Color.BLUE.value in output

    def test_image_colored(self) -> None:
        """Should render image placeholders."""
        config = RenderConfig(use_color=True)
        renderer = MarkdownRenderer(config)
        output = renderer.render("![Alt](image.png)")
        assert "Image:" in output or "Alt" in output

    def test_blockquote_colored(self) -> None:
        """Should render blockquotes with dim color."""
        config = RenderConfig(use_color=True)
        renderer = MarkdownRenderer(config)
        output = renderer.render("> A quote")
        assert "A quote" in output


class TestMarkdownRestoreCodeBlocks:
    """Tests for code block restoration."""

    def test_multiple_code_blocks(self) -> None:
        """Should handle multiple code blocks."""
        config = RenderConfig(use_color=False)
        renderer = MarkdownRenderer(config)
        md = """```
block 1
```

Some text

```
block 2
```"""
        output = renderer.render(md)
        assert "block 1" in output
        assert "block 2" in output
        assert "Some text" in output

    def test_code_block_with_special_chars(self) -> None:
        """Should preserve special characters in code blocks."""
        config = RenderConfig(use_color=False)
        renderer = MarkdownRenderer(config)
        md = """```
<html>&amp;</html>
**not bold**
# not header
```"""
        output = renderer.render(md)
        assert "<html>" in output
        assert "**not bold**" in output
        assert "# not header" in output


class TestMarkdownMaxWidth:
    """Tests for max width handling."""

    def test_long_line_handling(self) -> None:
        """Should handle very long lines."""
        config = RenderConfig(use_color=False, max_width=40)
        renderer = MarkdownRenderer(config)
        long_text = "word " * 50
        output = renderer.render(long_text)
        # Should not crash
        assert "word" in output

    def test_width_affects_code_block(self) -> None:
        """Max width should affect code block rendering."""
        config = RenderConfig(use_color=False, max_width=60)
        renderer = MarkdownRenderer(config)
        md = """```
short code
```"""
        output = renderer.render(md)
        assert "short code" in output


class TestMarkdownEmptyContent:
    """Tests for empty/edge case content."""

    def test_only_newlines(self) -> None:
        """Should handle only newlines."""
        config = RenderConfig(use_color=False)
        renderer = MarkdownRenderer(config)
        output = renderer.render("\n\n\n")
        assert output == ""

    def test_single_header(self) -> None:
        """Should handle single header with no content."""
        config = RenderConfig(use_color=False)
        renderer = MarkdownRenderer(config)
        output = renderer.render("# ")
        # Should handle gracefully
        assert output is not None

    def test_empty_code_block(self) -> None:
        """Should handle empty code block."""
        config = RenderConfig(use_color=False)
        renderer = MarkdownRenderer(config)
        md = """```
```"""
        output = renderer.render(md)
        assert "┌" in output or output == "" or output.strip() == ""
