import html as _html
import re
import urllib.request


_OG_RE = re.compile(
    r'<meta[^>]+property=["\']og:image(?::url)?["\'][^>]+content=["\'](https?://[^"\']+)'
    r'|<meta[^>]+content=["\'](https?://[^"\']+)["\'][^>]+property=["\']og:image(?::url)?["\']'
)

_BROWSER_UA = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
)


def fetch_og_image(articles):
    """Try each article URL in sequence; return first og:image found or ''."""
    for article in articles:
        link = article.get('link') if isinstance(article, dict) else getattr(article, 'link', None)
        if not link:
            continue
        try:
            req = urllib.request.Request(link, headers={'User-Agent': _BROWSER_UA})
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw_html = resp.read(32768).decode('utf-8', errors='ignore')
            m = _OG_RE.search(raw_html)
            if m:
                return _html.unescape(m.group(1) or m.group(2) or '')
        except Exception:
            continue
    return ''
