from utils.formatting import markdown_to_telegram_html


def test_bold_and_italic():
    assert markdown_to_telegram_html("**hi**") == "<b>hi</b>"
    assert markdown_to_telegram_html("say *hello* now") == "say <i>hello</i> now"


def test_headers_become_bold():
    assert markdown_to_telegram_html("### Title") == "<b>Title</b>"


def test_bullets():
    out = markdown_to_telegram_html("- one\n- two")
    assert "• one" in out and "• two" in out


def test_links():
    out = markdown_to_telegram_html("[site](https://example.com)")
    assert '<a href="https://example.com">site</a>' == out


def test_html_special_chars_escaped():
    out = markdown_to_telegram_html("a < b & c > d")
    assert "&lt;" in out and "&amp;" in out and "&gt;" in out


def test_table_rows_flattened_and_separator_dropped():
    md = "| A | B |\n|---|---|\n| 1 | 2 |"
    out = markdown_to_telegram_html(md)
    assert "A — B" in out
    assert "1 — 2" in out
    assert "---" not in out


def test_br_tags_become_newlines():
    out = markdown_to_telegram_html("line one<br>line two")
    assert out == "line one\nline two"
