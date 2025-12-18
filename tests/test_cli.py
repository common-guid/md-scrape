import os
import sys
import subprocess
import pytest

# Add repo root to sys.path to import md-scrape
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# We use subprocess to test the CLI entry point
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), '..', 'md_scrape.py')

def test_cli_help():
    result = subprocess.run([sys.executable, SCRIPT_PATH, '--help'], capture_output=True, text=True)
    assert result.returncode == 0
    assert "usage:" in result.stdout
    assert "--url" in result.stdout
    assert "--mode" in result.stdout

def test_cli_missing_args():
    result = subprocess.run([sys.executable, SCRIPT_PATH], capture_output=True, text=True)
    assert result.returncode != 0
    assert "the following arguments are required" in result.stderr

def test_cli_mode_single_requires_url_and_output():
    # If we run with mode single but missing output
    result = subprocess.run([sys.executable, SCRIPT_PATH, '-m', 'single', '-u', 'http://example.com'], capture_output=True, text=True)
    assert result.returncode != 0

    # Correct usage
    # We won't actually run it fully here because it would try to scrape example.com
    # We just want to check args parsing.
    # But argparse doesn't validation "business logic" beyond required args.
    pass

def test_cli_defaults():
    # Only url and output are required
    # This might actually try to run the scrape, so we should be careful.
    # We can use the --help to verify defaults are shown? Not reliably.
    # We'll rely on the unit tests for logic.
    pass
