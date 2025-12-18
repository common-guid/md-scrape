import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import md_scrape

# Mock Playwright to avoid actual network requests
@pytest.fixture
def mock_playwright():
    with patch("md_scrape.sync_playwright") as mock:
        yield mock

def test_scrape_single(mock_playwright, tmp_path):
    # Setup Mock
    mock_p = mock_playwright.return_value.__enter__.return_value
    mock_browser = mock_p.chromium.launch.return_value
    mock_page = mock_browser.new_page.return_value

    # Mock page content
    html_content = "<html><body><h1>Test Title</h1><p>Test Content</p></body></html>"
    mock_page.content.return_value = html_content

    url = "https://example.com/test-page"
    root_dir = "example.com"
    output_dir = str(tmp_path)

    md_scrape.scrape_single(url, output_dir, root_dir)

    # Verify file was created
    # Path should be output_dir/test-page.md
    expected_path = os.path.join(output_dir, "test-page.md")
    assert os.path.exists(expected_path)

    with open(expected_path, "r") as f:
        content = f.read()
        assert "# Test Title" in content
        assert "Test Content" in content

    # Verify no crawling occurred (only 1 goto)
    mock_page.goto.assert_called_once_with(url)

def test_scrape_crawl(mock_playwright, tmp_path):
    # Setup Mock
    mock_p = mock_playwright.return_value.__enter__.return_value
    mock_browser = mock_p.chromium.launch.return_value
    mock_page = mock_browser.new_page.return_value

    # Mock page content logic
    # First page links to second page
    def side_effect_goto(url):
        # We don't return anything from goto, but we set up content() for the next call
        pass

    mock_page.goto.side_effect = side_effect_goto

    # We need to change what content() returns based on the last visited URL,
    # but the mock logic is a bit simple here.
    # Instead, let's use a side_effect for content that checks the call args of goto?
    # Actually, page.content() is called AFTER page.goto().
    # So we can track state.

    current_url_container = {"url": ""}

    def side_effect_goto(url):
        current_url_container["url"] = url

    mock_page.goto.side_effect = side_effect_goto

    def side_effect_content():
        url = current_url_container["url"]
        if url == "https://example.com/start":
            return '<html><body><a href="/page2">Link</a></body></html>'
        elif url == "https://example.com/page2":
            return '<html><body><p>Page 2</p></body></html>'
        return ""

    mock_page.content.side_effect = side_effect_content

    start_url = "https://example.com/start"
    root_dir = "example.com"
    output_dir = str(tmp_path)

    md_scrape.scrape_crawl(start_url, output_dir, root_dir)

    # Verify files created
    # start -> start.md (or index.md if we handle it that way?)
    # url_to_filename(".../start") -> start.md
    assert os.path.exists(os.path.join(output_dir, "start.md"))
    assert os.path.exists(os.path.join(output_dir, "page2.md"))

    # Verify visited state files
    assert os.path.exists(os.path.join(output_dir, "visited_urls.txt"))
