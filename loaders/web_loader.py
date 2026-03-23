import requests
from bs4 import BeautifulSoup


def load_url(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; RAG-Bot/1.0)"}
    response = requests.get(url, timeout=15, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
        tag.decompose()

    # Prefer main content areas
    main = soup.find("main") or soup.find("article") or soup.body
    text = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)

    # Clean up excessive blank lines
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)
