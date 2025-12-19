import os
import re
import json
import argparse
import subprocess
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from markdownify import markdownify

# ---------------------------------------------------------
# ------------------- Utility Functions --------------------
# ---------------------------------------------------------

def sanitize_filename(name: str) -> str:
    """Remove illegal characters for filenames."""
    # We want to allow slashes if they are directory separators,
    # but this function is usually called on path segments.
    # However, if we pass a full relative path "subdir/file", we shouldn't sanitize the slash.
    # The previous implementation split by slash and sanitized parts. We will do the same in url_to_filename.
    return re.sub(r'[\\*?:"<>|]', '_', name)

def convert_html_to_markdown(html_content: str) -> str:
    """Convert HTML to Markdown (adjust markdownify settings as needed)."""
    return markdownify(html_content, heading_style="ATX")

def url_to_filename(url: str, root_dir: str, output_dir: str) -> str:
    """
    Convert a doc URL into a local .md file path based on root_dir.
    """
    parsed = urlparse(url)
    # Clean url path: hostname + path
    url_clean = (parsed.netloc + parsed.path).rstrip("/")

    # Clean root_dir: remove scheme if present
    if "://" in root_dir:
        r_parsed = urlparse(root_dir)
        root_clean = (r_parsed.netloc + r_parsed.path).rstrip("/")
    else:
        root_clean = root_dir.rstrip("/")

    # Calculate relative path
    if url_clean.startswith(root_clean):
        rel = url_clean[len(root_clean):]
    else:
        # If it doesn't match root_dir, use the full url_clean path
        # (effectively creating directories for hostname/path)
        rel = url_clean

    rel = rel.strip("/")
    if not rel:
        rel = "index"

    # Split into parts to sanitize filenames
    parts = rel.split("/")
    # Sanitize each part
    parts = [sanitize_filename(p) for p in parts]

    filename = parts[-1] + ".md"
    subdirs = parts[:-1]

    return os.path.join(output_dir, *subdirs, filename)

def rewrite_local_links(soup: BeautifulSoup, current_url: str, url_to_local: dict, root_dir: str, output_dir: str):
    """
    Rewrite <a> tags to point to local .md files using relative paths.
    """
    # Calculate where the current file is
    current_md_path = url_to_local.get(current_url)
    if not current_md_path:
        return

    # We only rewrite links that we know about (in url_to_local)
    # OR that we *should* know about?
    # In crawl mode, we populate url_to_local for all visited.
    # In single mode, we only have one entry.

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if not href or href.startswith("#"):
            continue

        absolute = urljoin(current_url, href)

        # In the original code, it checked: if BASE_URL not in absolute: continue
        # We should probably respect that "internal link" logic for rewriting.
        # But since we changed "BASE_URL" to "root_dir" or "hostname" scope,
        # let's just check if it's in url_to_local.

        target_md_path = url_to_local.get(absolute)

        if not target_md_path:
            # If we haven't visited it, maybe we can calculate where it WOULD be?
            # But if we aren't scraping it, a broken relative link is worse than an absolute link.
            # So, only rewrite if we have a local path for it.
            continue

        # Compute a relative path from current .md to the target .md
        try:
            relative_path = os.path.relpath(
                target_md_path,
                start=os.path.dirname(current_md_path)
            )
            a_tag["href"] = relative_path
        except ValueError:
            # In case of path issues
            pass

def save_bfs_state(visited, to_visit, url_to_local, output_dir):
    """Persist BFS sets/dict to files."""
    visited_path = os.path.join(output_dir, "visited_urls.txt")
    to_visit_path = os.path.join(output_dir, "to_visit_urls.txt")
    mapping_path = os.path.join(output_dir, "url_to_local.json")

    os.makedirs(output_dir, exist_ok=True)

    with open(visited_path, "w", encoding="utf-8") as f:
        for url in visited:
            f.write(url + "\n")

    with open(to_visit_path, "w", encoding="utf-8") as f:
        for url in to_visit:
            f.write(url + "\n")

    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(url_to_local, f, indent=2)

def load_bfs_state(output_dir):
    """Load BFS sets/dict from files."""
    visited_path = os.path.join(output_dir, "visited_urls.txt")
    to_visit_path = os.path.join(output_dir, "to_visit_urls.txt")
    mapping_path = os.path.join(output_dir, "url_to_local.json")

    visited = set()
    to_visit = set()
    url_to_local = {}

    if os.path.exists(visited_path):
        with open(visited_path, "r", encoding="utf-8") as f:
            for line in f:
                visited.add(line.strip())

    if os.path.exists(to_visit_path):
        with open(to_visit_path, "r", encoding="utf-8") as f:
            for line in f:
                to_visit.add(line.strip())

    if os.path.exists(mapping_path):
        with open(mapping_path, "r", encoding="utf-8") as f:
            url_to_local = json.load(f)

    return visited, to_visit, url_to_local

# ---------------------------------------------------------
# ---------------------- Scraper Modes ---------------------
# ---------------------------------------------------------

def scrape_single(url: str, output_dir: str, root_dir: str):
    """Scrape a single URL."""
    print(f"Scraping Single URL: {url}")

    local_path = url_to_filename(url, root_dir, output_dir)
    url_to_local = {url: local_path}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url)
            page.wait_for_load_state("domcontentloaded")
            html = page.content()

            soup = BeautifulSoup(html, "html.parser")

            # Rewrite links?
            # For single mode, we only have one file.
            # Links to other pages will not be in url_to_local, so they will stay absolute.
            rewrite_local_links(soup, url, url_to_local, root_dir, output_dir)

            md = convert_html_to_markdown(str(soup))

            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(md)
            print(f"Saved to {local_path}")

        except Exception as e:
            print(f"Error scraping {url}: {e}")
        finally:
            browser.close()

def scrape_crawl(start_url: str, output_dir: str, root_dir: str):
    """Crawl starting from start_url."""

    # Determine Scope (Hostname of start_url)
    start_parsed = urlparse(start_url)
    scope_domain = start_parsed.netloc

    print(f"Starting Crawl: {start_url}")
    print(f"Scope Domain: {scope_domain}")
    print(f"Root Dir for paths: {root_dir}")

    # Check for existing state
    visited, to_visit, url_to_local = load_bfs_state(output_dir)

    if not visited and not to_visit:
        to_visit = {start_url}
        url_to_local = {start_url: url_to_filename(start_url, root_dir, output_dir)}
    else:
        print(f"Resuming: {len(visited)} visited, {len(to_visit)} to_visit.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            while to_visit:
                url = to_visit.pop()
                if url in visited:
                    continue

                visited.add(url)
                print(f"Scraping: {url}")

                if url not in url_to_local:
                    url_to_local[url] = url_to_filename(url, root_dir, output_dir)

                try:
                    page.goto(url)
                    page.wait_for_load_state("domcontentloaded")
                    html = page.content()
                except Exception as e:
                    print(f"Error loading {url}: {e}")
                    save_bfs_state(visited, to_visit, url_to_local, output_dir)
                    continue

                soup = BeautifulSoup(html, "html.parser")

                # Extract new links
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    if not href or href.startswith("#"):
                        continue

                    absolute = urljoin(url, href)

                    # Scope Check
                    # We use scope_domain to limit crawling to the same site
                    abs_parsed = urlparse(absolute)
                    if abs_parsed.netloc == scope_domain:
                        if absolute not in visited:
                            to_visit.add(absolute)
                        if absolute not in url_to_local:
                            url_to_local[absolute] = url_to_filename(absolute, root_dir, output_dir)

                rewrite_local_links(soup, url, url_to_local, root_dir, output_dir)
                md = convert_html_to_markdown(str(soup))

                local_path = url_to_local[url]
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, "w", encoding="utf-8") as f:
                    f.write(md)

                save_bfs_state(visited, to_visit, url_to_local, output_dir)

        except KeyboardInterrupt:
            print("\nInterrupted by user. Saving BFS state...")
            save_bfs_state(visited, to_visit, url_to_local, output_dir)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            save_bfs_state(visited, to_visit, url_to_local, output_dir)
        finally:
            browser.close()

    print("\nCrawl complete.")
    print(f"Visited: {len(visited)}")
    print(f"Remaining: {len(to_visit)}")

# ---------------------------------------------------------
# ---------------------- Main Logic ------------------------
# ---------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Markdown Scraper")
    parser.add_argument("-u", "--url", required=True, help="The URL to scrape (or start scraping from)")
    parser.add_argument("-o", "--output", required=True, help="The output directory")
    parser.add_argument("-m", "--mode", choices=["crawl", "single"], default="crawl", help="Scraping mode: 'crawl' (default) or 'single'")
    parser.add_argument("--root-dir", help="The root directory for calculating file structure (defaults to hostname of URL)")

    args = parser.parse_args()

    url = args.url
    output_dir = args.output
    mode = args.mode
    root_dir = args.root_dir

    if not root_dir:
        # Default to hostname
        parsed = urlparse(url)
        root_dir = parsed.netloc

    if mode == "single":
        scrape_single(url, output_dir, root_dir)
    else:
        scrape_crawl(url, output_dir, root_dir)

    # Note: Utility script integration is disabled for CLI mode per requirements.

if __name__ == "__main__":
    main()
