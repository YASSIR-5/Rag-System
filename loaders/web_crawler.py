import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque


def crawl_site(start_url: str, max_pages: int = 50) -> list[dict]:
    """
    Crawl all pages on the same domain as start_url.
    Returns list of {url, text} dicts.
    """
    parsed = urlparse(start_url)
    base_domain = parsed.netloc
    base_scheme = parsed.scheme

    visited = set()
    queue = deque([start_url])
    results = []

    headers = {"User-Agent": "Mozilla/5.0 (compatible; RAG-Crawler/1.0)"}

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, timeout=10, headers=headers)
            resp.raise_for_status()
            if 'text/html' not in resp.headers.get('Content-Type', ''):
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract text
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            main = soup.find("main") or soup.find("article") or soup.body
            text = main.get_text(separator="\n", strip=True) if main else ""
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            clean_text = "\n".join(lines)

            if len(clean_text) > 100:
                results.append({"url": url, "text": clean_text})

            # Find links on same domain
            for a in soup.find_all("a", href=True):
                href = a["href"]
                full_url = urljoin(url, href)
                p = urlparse(full_url)
                if p.netloc == base_domain and p.scheme in ("http", "https"):
                    clean = full_url.split("#")[0]
                    if clean not in visited:
                        queue.append(clean)

        except Exception:
            continue

    return results
