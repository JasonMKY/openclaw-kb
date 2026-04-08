import base64
import io
import re
from typing import Optional

import httpx


async def parse_content(content: str, content_type: str) -> tuple[str, Optional[str]]:
    """
    Parse raw content into plain text.
    Returns (text, detected_title).
    """
    if content_type == "text":
        return content, None

    elif content_type == "markdown":
        text = _strip_markdown(content)
        # Try to grab first heading as title
        title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else None
        return text, title

    elif content_type == "pdf_base64":
        return await _parse_pdf(content)

    elif content_type == "url":
        return await _fetch_url(content)

    else:
        raise ValueError(f"Unknown content type: {content_type}")


def _strip_markdown(md: str) -> str:
    """Remove common markdown syntax, returning clean text."""
    # Remove code blocks
    md = re.sub(r"```[\s\S]*?```", "", md)
    md = re.sub(r"`[^`]+`", "", md)
    # Remove headings markers
    md = re.sub(r"^#{1,6}\s+", "", md, flags=re.MULTILINE)
    # Remove bold/italic
    md = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", md)
    md = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", md)
    # Remove links, keep text
    md = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", md)
    # Remove images
    md = re.sub(r"!\[[^\]]*\]\([^\)]+\)", "", md)
    # Remove horizontal rules
    md = re.sub(r"^[-*_]{3,}\s*$", "", md, flags=re.MULTILINE)
    # Remove blockquotes
    md = re.sub(r"^>\s+", "", md, flags=re.MULTILINE)
    # Collapse whitespace
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


async def _parse_pdf(b64_data: str) -> tuple[str, Optional[str]]:
    """Extract text from a base64-encoded PDF."""
    try:
        import pypdf
    except ImportError:
        raise RuntimeError("pypdf not installed. Run: pip install pypdf")

    pdf_bytes = base64.b64decode(b64_data)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    full_text = "\n\n".join(pages)
    return full_text, None


async def _fetch_url(url: str) -> tuple[str, Optional[str]]:
    """Fetch a URL and extract clean text using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError("beautifulsoup4 not installed. Run: pip install beautifulsoup4 lxml")

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "OpenClawBot/1.0"})
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # Extract title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    # Remove noise tags
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    # Get main content preferring article/main tags
    main = soup.find("article") or soup.find("main") or soup.find("body")
    text = main.get_text(separator="\n", strip=True) if main else soup.get_text(separator="\n", strip=True)

    # Collapse blank lines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, title
