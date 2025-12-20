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

def test_scope_comprehensive(mock_playwright, tmp_path):
    # Setup Mock
    mock_p = mock_playwright.return_value.__enter__.return_value
    mock_browser = mock_p.chromium.launch.return_value
    mock_context = mock_browser.new_context.return_value
    mock_page = mock_context.new_page.return_value

    current_url_container = {"url": ""}

    # We will simulate a site with 20+ pages to test various scenarios
    # Structure:
    # Start (Out) ->
    #   Level1_In (Scope) -> Level2_In (Scope)
    #   Level1_Out (Out) -> Level2_In_Deep (Scope)
    #   Level1_Mix (Out) ->
    #       Level2_Out (Out) -> Level3_In (Scope)
    #       Level2_Mixed (Scope) -> Level3_Out (Out)

    # 15 Test Cases of pages that should/shouldn't be saved:
    # 1. Start (Out) -> Saved because it's start_url
    # 2. Level1_In (Scope) -> Saved
    # 3. Level2_In (Scope) -> Saved
    # 4. Level1_Out (Out) -> Visited, Not Saved
    # 5. Level2_In_Deep (Scope) -> Saved
    # 6. Level1_Mix (Out) -> Visited, Not Saved
    # 7. Level2_Out (Out) -> Visited, Not Saved
    # 8. Level3_In (Scope) -> Saved
    # 9. Level2_Mixed (Scope) -> Saved
    # 10. Level3_Out (Out) -> Visited, Not Saved

    # Extra variants for substring matching:
    # 11. Partial Scope Match (e.g. scope="foo", url=".../foobar") -> Saved
    # 12. Partial Scope Mismatch (e.g. scope="foo", url=".../bar") -> Not Saved
    # 13. Scope in Query Param (e.g. scope="foo", url="...?q=foo") -> Saved (technically in URL)
    # 14. Scope in Domain (e.g. scope="example", url="example.com") -> Saved (technically in URL)
    # 15. Root Dir collision -> Handling

    site_map = {
        "https://example.com/start": [
            "/scope/level1",            # Case 2
            "/out/level1",              # Case 4
            "/mix/level1",              # Case 6
            "/foobar/partial",          # Case 11
            "/bar/mismatch",            # Case 12
            "/query?q=scope",           # Case 13
        ],
        "https://example.com/scope/level1": ["/scope/level2"], # Case 3
        "https://example.com/scope/level2": [],
        "https://example.com/out/level1": ["/scope/level2_deep"], # Case 5
        "https://example.com/scope/level2_deep": [],
        "https://example.com/mix/level1": ["/out/level2", "/scope/level2_mixed"], # Case 7, 9
        "https://example.com/out/level2": ["/scope/level3"], # Case 8
        "https://example.com/scope/level3": [],
        "https://example.com/scope/level2_mixed": ["/out/level3"], # Case 10
        "https://example.com/out/level3": [],
        "https://example.com/foobar/partial": [],
        "https://example.com/bar/mismatch": [],
        "https://example.com/query?q=scope": [],
    }

    def side_effect_goto(url):
        current_url_container["url"] = url

    mock_page.goto.side_effect = side_effect_goto

    def side_effect_content():
        url = current_url_container["url"]
        links = site_map.get(url, [])
        html = "<html><body>"
        for link in links:
            html += f'<a href="{link}">Link</a>'
        html += "</body></html>"
        return html

    mock_page.content.side_effect = side_effect_content

    start_url = "https://example.com/start"
    root_dir = "example.com"
    output_dir = str(tmp_path)
    scope = "scope"
    # Using "scope" as substring.
    # URLs containing "scope" should be saved.
    # URLs NOT containing "scope" should NOT be saved (unless start_url).

    md_scrape.scrape_crawl(start_url, output_dir, root_dir, scope=scope)

    # Helper to check existence
    def check_exists(rel_path):
        return os.path.exists(os.path.join(output_dir, *rel_path.split("/")))

    # 1. Start URL (Out of scope, but entry point) -> Saved
    # Filename: start.md
    assert check_exists("start.md"), "Case 1: Start URL should be saved"

    # 2. Level1_In (Contains 'scope') -> Saved
    # Filename: scope/level1.md
    assert check_exists("scope/level1.md"), "Case 2: In-scope URL should be saved"

    # 3. Level2_In (Contains 'scope') -> Saved
    assert check_exists("scope/level2.md"), "Case 3: Deep in-scope URL should be saved"

    # 4. Level1_Out (No 'scope') -> Not Saved
    # Filename: out/level1.md
    assert not check_exists("out/level1.md"), "Case 4: Out-of-scope URL should not be saved"

    # 5. Level2_In_Deep (Contains 'scope', child of Out) -> Saved
    assert check_exists("scope/level2_deep.md"), "Case 5: In-scope child of out-of-scope parent should be saved"

    # 6. Level1_Mix (No 'scope') -> Not Saved
    assert not check_exists("mix/level1.md"), "Case 6: Out-of-scope URL should not be saved"

    # 7. Level2_Out (No 'scope') -> Not Saved
    assert not check_exists("out/level2.md"), "Case 7: Deep out-of-scope URL should not be saved"

    # 8. Level3_In (Contains 'scope', child of Out->Out) -> Saved
    assert check_exists("scope/level3.md"), "Case 8: Deep in-scope child of multiple out-of-scope parents should be saved"

    # 9. Level2_Mixed (Contains 'scope') -> Saved
    assert check_exists("scope/level2_mixed.md"), "Case 9: In-scope URL should be saved"

    # 10. Level3_Out (No 'scope', child of In) -> Not Saved
    assert not check_exists("out/level3.md"), "Case 10: Out-of-scope child of in-scope parent should not be saved"

    # 11. Partial Match (Contains 'scope' in 'foobar'?? No wait)
    # Scope is "scope". "foobar" does not contain "scope".
    # Wait, I set scope="scope".
    # My test setup for Case 11 was "/foobar/partial".
    # "foobar" doesn't contain "scope". "partial" doesn't.
    # Ah, I should use a path that contains "scope" as substring but not exact path component.
    # E.g. "/telescope/view".
    # Let's adjust the assert. "foobar" should FAIL scope check.
    assert not check_exists("foobar/partial.md"), "Case 11: 'foobar' does not contain 'scope', should not be saved"

    # Let's add a real partial match case manually
    # URL: https://example.com/telescope/view (contains "scope")
    # I didn't add it to site_map.
    # But I added "/query?q=scope".

    # 13. Query Param (Contains 'scope') -> Saved
    # Filename: query.md? No, url_to_filename cleans query params usually?
    # Let's check url_to_filename logic.
    # parsed.netloc + parsed.path. Query is ignored.
    # So "query?q=scope" -> path is "/query".
    # Filename: query.md.
    # Scope check uses `url` (full url string).
    # So "scope" IS in "https://example.com/query?q=scope".
    # So it SHOULD be saved.
    assert check_exists("query.md"), "Case 13: Scope in query param should trigger save"

    # 12. Mismatch (No 'scope') -> Not Saved
    assert not check_exists("bar/mismatch.md"), "Case 12: Mismatch should not be saved"

    # 14. Domain match?
    # If scope="example", everything matches "example.com".
    # My scope is "scope".
    # So not applicable here.

    # 15. Check visited count
    # Visited should include ALL pages (13 pages in site_map).
    # Start + 5 children + level2s + level3s...
    # Wait, `visited` set tracks URLs we successfully loaded.
    # All should be loaded.

    visited_file = os.path.join(output_dir, "visited_urls.txt")
    with open(visited_file, "r") as f:
        visited_count = len(f.readlines())

    # Total unique URLs in site_map: 1 + 6 + 1 + 1 + 2 + 1 + 1 = 13.
    assert visited_count == 13, f"All 13 reachable pages should be visited for discovery, got {visited_count}"
