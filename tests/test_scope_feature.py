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

def test_scrape_crawl_with_scope(mock_playwright, tmp_path):
    # Setup Mock
    mock_p = mock_playwright.return_value.__enter__.return_value
    mock_browser = mock_p.chromium.launch.return_value
    mock_page = mock_browser.new_page.return_value

    current_url_container = {"url": ""}

    def side_effect_goto(url):
        current_url_container["url"] = url

    mock_page.goto.side_effect = side_effect_goto

    def side_effect_content():
        url = current_url_container["url"]
        if url == "https://example.com/start":
            # Two links: one in scope, one out of scope
            return '''
            <html><body>
                <a href="/guides/concepts/page1">In Scope</a>
                <a href="/other/page2">Out of Scope</a>
            </body></html>
            '''
        elif url == "https://example.com/guides/concepts/page1":
            # Link to another in-scope page
            return '''
            <html><body>
                <a href="/guides/concepts/page3">Deep In Scope</a>
            </body></html>
            '''
        elif url == "https://example.com/guides/concepts/page3":
            return '<html><body><p>Deep Content</p></body></html>'
        elif url == "https://example.com/other/page2":
            return '<html><body><p>Should Not Be Visited</p></body></html>'
        return ""

    mock_page.content.side_effect = side_effect_content

    start_url = "https://example.com/start"
    root_dir = "example.com"
    output_dir = str(tmp_path)
    scope = "guides/concepts"

    # Call scrape_crawl with the new scope argument
    md_scrape.scrape_crawl(start_url, output_dir, root_dir, scope=scope)

    # Verify files created

    # Start page should always be visited
    assert os.path.exists(os.path.join(output_dir, "start.md"))

    # In-scope page should be visited
    # URL: https://example.com/guides/concepts/page1 -> guides/concepts/page1.md
    assert os.path.exists(os.path.join(output_dir, "guides", "concepts", "page1.md"))

    # Deep in-scope page should be visited
    assert os.path.exists(os.path.join(output_dir, "guides", "concepts", "page3.md"))

    # Out-of-scope page should NOT be visited
    # URL: https://example.com/other/page2 -> other/page2.md
    assert not os.path.exists(os.path.join(output_dir, "other", "page2.md"))
