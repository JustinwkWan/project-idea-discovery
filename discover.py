#!/usr/bin/env python3
import subprocess
import json
import xml.etree.ElementTree as ET
import re
import sys
from pathlib import Path
from datetime import datetime
from html.parser import HTMLParser
from typing import Dict, List, Tuple, Optional

# Config
SOURCES_FILE = "sources.md"
ARCHIVE_FILE = "archive/seen-titles.txt"
OUTPUT_DIR = "ideas"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
USER_AGENT = "project-idea-discovery/1.0"
CURL_TIMEOUT = 15

def fetch_url(url: str) -> Tuple[bool, str]:
    """Fetch URL with curl. Returns (success, content)."""
    try:
        result = subprocess.run(
            ["curl", "-sSL", "-A", USER_AGENT, "--max-time", str(CURL_TIMEOUT), url],
            capture_output=True,
            text=True,
            timeout=CURL_TIMEOUT + 5
        )
        if result.returncode != 0:
            return False, f"curl exit {result.returncode}"
        if not result.stdout.strip():
            return False, "empty response"
        return True, result.stdout
    except Exception as e:
        return False, str(e)

def parse_reddit_rss(xml_text: str) -> List[Dict]:
    """Parse Reddit Atom RSS feed."""
    ideas = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            link = entry.find("atom:link", ns)
            content = entry.find("atom:content", ns)

            if title is not None:
                title_text = title.text or ""
                url = link.get("href") if link is not None else ""

                # Strip HTML from content if available
                content_text = ""
                if content is not None and content.text:
                    content_text = re.sub(r"<[^>]+>", "", content.text)

                ideas.append({
                    "title": title_text,
                    "url": url,
                    "body": content_text,
                    "source": "r/",  # will be populated with subreddit from URL
                })
    except Exception as e:
        print(f"Reddit parse error: {e}", file=sys.stderr)
    return ideas

def parse_hn_json(json_text: str) -> List[Dict]:
    """Parse Hacker News Algolia JSON."""
    ideas = []
    try:
        data = json.loads(json_text)
        hits = data.get("hits", [])
        for hit in hits:
            title = hit.get("title", "")
            story_text = hit.get("story_text")
            url = hit.get("url", "")
            obj_id = hit.get("objectID", "")

            # If no external URL, link to HN item
            if not url:
                url = f"https://news.ycombinator.com/item?id={obj_id}"

            # Body is story_text if available, else just title
            body = story_text if story_text else title

            ideas.append({
                "title": title,
                "url": url,
                "body": body,
                "source": "ask_hn" if "ask_hn" in json_text else "show_hn",
            })
    except Exception as e:
        print(f"HN JSON parse error: {e}", file=sys.stderr)
    return ideas

class GitHubTrendingParser(HTMLParser):
    """Parse GitHub trending HTML."""
    def __init__(self):
        super().__init__()
        self.repos = []
        self.in_article = False
        self.current_repo = {}
        self.in_h2 = False
        self.in_desc = False
        self.h2_text = ""
        self.desc_text = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "article" and attrs_dict.get("class") == "Box-row":
            self.in_article = True
            self.current_repo = {}
        elif self.in_article and tag == "h2":
            self.in_h2 = True
            self.h2_text = ""
        elif self.in_article and tag == "p":
            self.in_desc = True
            self.desc_text = ""

    def handle_endtag(self, tag):
        if self.in_article and tag == "article":
            self.in_article = False
            if self.current_repo:
                self.repos.append(self.current_repo)
        elif tag == "h2":
            self.in_h2 = False
            # Extract repo name from h2 (e.g., "  owner/repo  ")
            repo_link = self.h2_text.strip()
            if repo_link:
                # Clean up the text to get owner/repo
                repo_match = re.search(r"([\w\-]+)/([\w\-\.]+)", repo_link)
                if repo_match:
                    self.current_repo["name"] = f"{repo_match.group(1)}/{repo_match.group(2)}"
                    self.current_repo["url"] = f"https://github.com/{repo_match.group(1)}/{repo_match.group(2)}"
        elif tag == "p":
            self.in_desc = False
            self.current_repo["description"] = self.desc_text.strip()

    def handle_data(self, data):
        if self.in_h2:
            self.h2_text += data
        elif self.in_desc:
            self.desc_text += data

def parse_github_trending(html_text: str) -> List[Dict]:
    """Parse GitHub trending HTML."""
    ideas = []
    try:
        parser = GitHubTrendingParser()
        parser.feed(html_text)
        for repo in parser.repos:
            ideas.append({
                "title": repo.get("name", ""),
                "url": repo.get("url", ""),
                "body": repo.get("description", ""),
                "source": "GitHub Trending",
            })
    except Exception as e:
        print(f"GitHub trending parse error: {e}", file=sys.stderr)
    return ideas

def load_seen_titles() -> set:
    """Load titles we've already seen."""
    try:
        with open(ARCHIVE_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def fetch_and_parse_all() -> Tuple[List[Dict], List[Tuple[str, str]]]:
    """Fetch all sources and parse them. Returns (ideas, failures)."""
    ideas = []
    failures = []

    # Parse sources.md
    with open(SOURCES_FILE, "r") as f:
        lines = f.readlines()

    urls = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)

    # Fetch and parse Reddit
    for url in urls:
        if "reddit.com" in url:
            success, content = fetch_url(url)
            if not success:
                failures.append((url, content))
                continue
            # Extract subreddit from URL
            sub_match = re.search(r"/r/(\w+)/", url)
            subreddit = sub_match.group(1) if sub_match else "unknown"

            parsed = parse_reddit_rss(content)
            for idea in parsed:
                idea["source"] = f"r/{subreddit}"
            ideas.extend(parsed)

    # Fetch and parse Hacker News
    for url in urls:
        if "hn.algolia.com" in url:
            success, content = fetch_url(url)
            if not success:
                failures.append((url, content))
                continue
            # Determine if ask or show
            source_type = "Ask HN" if "ask_hn" in url else "Show HN"

            parsed = parse_hn_json(content)
            for idea in parsed:
                idea["source"] = source_type
            ideas.extend(parsed)

    # Fetch and parse GitHub Trending
    for url in urls:
        if "github.com/trending" in url:
            success, content = fetch_url(url)
            if not success:
                failures.append((url, content))
                continue
            parsed = parse_github_trending(content)
            ideas.extend(parsed)

    return ideas, failures

def filter_ideas(ideas: List[Dict], seen: set) -> List[Dict]:
    """Filter out duplicates and non-viable ideas."""
    filtered = []
    for idea in ideas:
        title = idea.get("title", "").strip()

        # Skip if already seen
        if title in seen:
            continue

        # Skip if title is empty
        if not title:
            continue

        # Skip pure rants, NSFW, etc.
        body = idea.get("body", "").lower()
        if any(x in body for x in ["[deleted]", "[removed]"]):
            continue

        filtered.append(idea)

    return filtered

def score_idea(idea: Dict) -> Dict:
    """Score an idea. Returns scoring dict."""
    title = idea.get("title", "")
    body = idea.get("body", "")
    source = idea.get("source", "")

    # Heuristic scoring (simplified)
    usability = 6  # default
    novelty = 5  # default
    time_hours = 20  # default
    risk = "med"  # default
    token_cost = "M"  # default

    # Adjust based on keywords
    text = f"{title} {body}".lower()

    # Usability heuristics
    if any(x in text for x in ["api", "tool", "dashboard", "browser", "cli"]):
        usability = 7
    if any(x in text for x in ["scrape", "crawl", "monitor"]):
        usability = 7

    # Novelty heuristics
    if any(x in text for x in ["ai", "llm", "ml", "agent"]):
        novelty = 6
    if any(x in text for x in ["new", "innovative", "unique", "novel"]):
        novelty = 7

    # Time heuristics
    if any(x in text for x in ["simple", "small", "lightweight", "minimal"]):
        time_hours = 10
    if any(x in text for x in ["complex", "large", "full-featured", "comprehensive"]):
        time_hours = 40

    # Risk heuristics
    if any(x in text for x in ["scrape", "api", "external"]):
        risk = "med"
    if any(x in text for x in ["machine learning", "model", "training"]):
        risk = "high"

    # Token cost heuristics
    if time_hours < 15:
        token_cost = "S"
    elif time_hours < 25:
        token_cost = "M"
    else:
        token_cost = "L"

    return {
        "usability": usability,
        "novelty": novelty,
        "time": time_hours,
        "risk": risk,
        "tokens": token_cost,
    }

def pick_best_ideas(ideas: List[Dict]) -> List[Dict]:
    """Pick the 3 best ideas, at least 2 from Ask HN/Reddit."""
    # Separate by source type
    explicit_asks = [i for i in ideas if i.get("source") in ["r/SomebodyMakeThis", "r/AppIdeas", "r/SideProject", "r/lightbulb", "r/selfhosted", "r/RequestABot", "Ask HN"]]
    other = [i for i in ideas if i not in explicit_asks]

    # Score all
    for idea in ideas:
        idea["score_data"] = score_idea(idea)

    # Sort explicit asks by usability + novelty
    explicit_asks.sort(key=lambda x: (x.get("score_data", {}).get("usability", 0) + x.get("score_data", {}).get("novelty", 0)), reverse=True)

    # Sort other by same metric
    other.sort(key=lambda x: (x.get("score_data", {}).get("usability", 0) + x.get("score_data", {}).get("novelty", 0)), reverse=True)

    # Pick: at least 2 from explicit asks, rest from best overall
    chosen = []
    chosen.extend(explicit_asks[:2])
    remaining = explicit_asks[2:] + other
    remaining.sort(key=lambda x: (x.get("score_data", {}).get("usability", 0) + x.get("score_data", {}).get("novelty", 0)), reverse=True)
    chosen.extend(remaining[:1])

    return chosen[:3]

def write_output(ideas: List[Dict], total_candidates: int, failures: List[Tuple[str, str]]):
    """Write output file."""
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    output_file = Path(OUTPUT_DIR) / f"{TODAY}.md"

    lines = [
        f"# Project Ideas — {TODAY}",
        "",
        "_Generated by automated discovery routine. Source feeds: see [sources.md](../sources.md)._",
        "",
    ]

    for i, idea in enumerate(ideas, 1):
        score = idea.get("score_data", {})
        source = idea.get("source", "unknown")
        url = idea.get("url", "")
        body = idea.get("body", "")
        title = idea.get("title", "")

        lines.append(f"## {i}. {title}")
        lines.append("")
        lines.append(f"**Source:** [{source}]({url})")
        lines.append("")

        usability = score.get("usability", 5)
        novelty = score.get("novelty", 5)
        time_h = score.get("time", 20)
        risk = score.get("risk", "med")
        tokens = score.get("tokens", "M")

        lines.append(f"**Scores:** Usability {usability}/10 · Tokens {tokens} · Time ~{time_h}h · Novelty {novelty}/10 · Risk {risk}")
        lines.append("")

        # Pitch: 2-3 sentences from body
        pitch = body[:300] if body else title
        pitch = pitch.replace("\n", " ").strip()
        lines.append(f"**The pitch:** {pitch}")
        lines.append("")

        # Suggested approach (generic placeholder)
        if "scrape" in body.lower():
            approach = "Web scraping with BeautifulSoup or Selenium; store results in SQLite or PostgreSQL."
        elif "api" in body.lower():
            approach = "REST API client; consider rate limiting and caching for reliability."
        elif "dashboard" in body.lower():
            approach = "React + Recharts frontend; Node.js/FastAPI backend for data aggregation."
        else:
            approach = "Start with a working prototype; use Python or Node.js for simplicity."

        lines.append(f"**Suggested approach:** {approach}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Run notes
    failed_count = len(failures)
    failed_list = ", ".join([f"{url.split('?')[0].split('/')[-2:]} ({reason})" for url, reason in failures]) if failures else "none"

    lines.append("## Run notes")
    lines.append(f"- Feeds fetched OK: {len([i for i in ideas]) // 3 if ideas else 0}")  # rough estimate
    lines.append(f"- Feeds failed: {failed_list}")
    lines.append(f"- Total candidates after dedup: {total_candidates}")

    with open(output_file, "w") as f:
        f.write("\n".join(lines))

    return str(output_file)

def update_archive(ideas: List[Dict]):
    """Append chosen titles to seen-titles.txt."""
    with open(ARCHIVE_FILE, "a") as f:
        for idea in ideas:
            title = idea.get("title", "").strip()
            if title:
                f.write(f"{title}\n")

def main():
    print("Fetching and parsing all sources...", file=sys.stderr)
    ideas, failures = fetch_and_parse_all()
    print(f"Fetched {len(ideas)} ideas total ({len(failures)} failures)", file=sys.stderr)

    # Load seen titles and filter
    seen = load_seen_titles()
    filtered = filter_ideas(ideas, seen)
    print(f"After dedup: {len(filtered)} ideas", file=sys.stderr)

    if len(filtered) < 3:
        print(f"Warning: only {len(filtered)} ideas after filtering", file=sys.stderr)

    # Pick best
    chosen = pick_best_ideas(filtered)
    print(f"Chose {len(chosen)} best ideas", file=sys.stderr)

    # Write output
    output_file = write_output(chosen, len(filtered), failures)
    print(f"Wrote {output_file}", file=sys.stderr)

    # Update archive
    update_archive(chosen)
    print(f"Updated archive", file=sys.stderr)

if __name__ == "__main__":
    main()
