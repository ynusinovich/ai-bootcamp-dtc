import os
import time
import urllib.parse
import requests

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_RAW = "https://en.wikipedia.org/w/index.php"

def _headers():
    # Set your contact so Wikimedia can reach you if needed (API etiquette)
    contact = os.getenv("WIKI_AGENT_CONTACT", "your-email@example.com")
    return {
        "User-Agent": f"WikiAgentBootcamp/0.1 (contact: {contact})",
        "Accept": "application/json",
    }


def search_wikipedia(query: str, limit: int = 5) -> dict:
    """
    Search Wikipedia using the Action API.
    Returns dict with lightweight entries: [{'title': 'Capybara', 'snippet': '...'}, ...]
    """
    # Homework asked to replace spaces with '+'
    encoded = query.replace(" ", "+")
    params = {
        "action": "query",
        "format": "json",
        "list": "search",
        "srsearch": encoded,
        "srlimit": max(1, min(int(limit), 10)),
    }
    r = requests.get(WIKI_API, params=params, headers=_headers(), timeout=20)
    r.raise_for_status()
    data = r.json()
    results = data.get("query", {}).get("search", [])
    # Be nice to the API: small pause (etiquette encourages serial requests)
    time.sleep(0.3)
    return [{"title": it["title"], "snippet": it.get("snippet", "")} for it in results]  # type: ignore


def get_page_raw(title: str) -> dict:
    """
    Get raw wikitext for a page via index.php?action=raw.
    Returns dict: {'title': title, 'url': 'https://en.wikipedia.org/wiki/Title', 'content': '...'}
    """
    # Wikipedia canonical URL uses underscores
    safe_title = title.replace(" ", "_")
    url = f"{WIKI_RAW}?title={urllib.parse.quote(safe_title)}&action=raw"
    r = requests.get(url, headers=_headers(), timeout=20)
    r.raise_for_status()
    content = r.text
    time.sleep(0.3)
    return {
        "title": title,
        "url": f"https://en.wikipedia.org/wiki/{safe_title}",
        "content": content,
    }
