import os
import sys
import pytest

# Add repo root to sys.path to import md-scrape
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from md_scrape import url_to_filename

def test_url_to_filename_with_root_dir_match():
    # User Example
    # URL: https://docs.crewai.com/en/guides/concepts/evaluating-use-cases
    # Root: docs.crewai.com/en/guides
    # Output: /home/docs
    # Expected: /home/docs/concepts/evaluating-use-cases.md

    url = "https://docs.crewai.com/en/guides/concepts/evaluating-use-cases"
    root_dir = "docs.crewai.com/en/guides"
    output_dir = "/home/docs"

    result = url_to_filename(url, root_dir, output_dir)

    # Check suffix
    assert result.endswith("concepts/evaluating-use-cases.md")
    # Check full path
    expected = os.path.join(output_dir, "concepts", "evaluating-use-cases.md")
    assert result == expected

def test_url_to_filename_with_root_dir_match_trailing_slash():
    url = "https://docs.crewai.com/en/guides/concepts/evaluating-use-cases/"
    root_dir = "docs.crewai.com/en/guides"
    output_dir = "/home/docs"

    result = url_to_filename(url, root_dir, output_dir)
    expected = os.path.join(output_dir, "concepts", "evaluating-use-cases.md")
    assert result == expected

def test_url_to_filename_root_dir_includes_scheme():
    # If user provides scheme in root_dir, it should still work
    url = "https://docs.crewai.com/en/guides/foo"
    root_dir = "https://docs.crewai.com/en/guides"
    output_dir = "out"

    result = url_to_filename(url, root_dir, output_dir)
    expected = os.path.join(output_dir, "foo.md")
    assert result == expected

def test_url_to_filename_default_hostname():
    # If root_dir is just hostname (default behavior)
    url = "https://example.com/foo/bar"
    root_dir = "example.com"
    output_dir = "out"

    result = url_to_filename(url, root_dir, output_dir)
    expected = os.path.join(output_dir, "foo", "bar.md")
    assert result == expected

def test_url_to_filename_no_match():
    # If URL is totally different from root_dir
    # It should probably just dump it in output_dir using the full path
    url = "https://other.com/foo"
    root_dir = "example.com"
    output_dir = "out"

    result = url_to_filename(url, root_dir, output_dir)
    # path is other.com/foo -> other_com/foo.md (sanitized)
    # "other.com" might be sanitized to "other_com" or similar

    # Let's check what sanitization does.
    # url_clean = "other.com/foo"
    # rel = "other.com/foo"
    # parts = ["other.com", "foo"] -> ["other.com", "foo"] (dot is legal)

    expected = os.path.join(output_dir, "other.com", "foo.md")
    assert result == expected
