import json
import re
import urllib.request
from flask import Blueprint, jsonify
from server.services.cache import cached

bp = Blueprint('widget_apple_bbc', __name__, url_prefix='/api')

_BBC_LIVE_URL = 'https://www.bbc.com/live/news'
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', re.DOTALL)


@cached(ttl=300)
def _fetch():
    req = urllib.request.Request(_BBC_LIVE_URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=8) as resp:
        html = resp.read().decode('utf-8', errors='replace')

    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise ValueError('__NEXT_DATA__ not found')
    data = json.loads(m.group(1))

    page = data.get('props', {}).get('pageProps', {}).get('page', {})
    page_obj = next((v for v in page.values() if isinstance(v, dict)), {}) if isinstance(page, dict) else {}
    sections = page_obj.get('sections', [])
    content = sections[0].get('content', []) if sections else []

    items = []
    for c in content:
        title = (c.get('title') or '').strip()
        if not title:
            continue
        img_src = ''
        try:
            img_src = c['image']['model']['blocks'].get('src', '') or ''
        except (KeyError, TypeError):
            pass
        items.append({
            'title': title,
            'link': c.get('href', ''),
            'isLive': bool(c.get('isLiveNow')),
            'lastUpdated': (c.get('metadata') or {}).get('lastUpdated'),
            'description': c.get('description', ''),
            'image': img_src,
        })
        if len(items) >= 10:
            break
    return items


@bp.route('/bbc_news')
def bbc_news():
    try:
        return jsonify(_fetch())
    except Exception as e:
        print(f"[bbc] fetch failed: {e}")
        return jsonify([]), 502
