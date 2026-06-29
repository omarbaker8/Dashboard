import json
import urllib.request
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, request, jsonify
from server.services.cache import cached
from server.services.og_scraper import fetch_og_image

bp = Blueprint('widget_kagi_news', __name__, url_prefix='/api')

_KAGI_API_BASE = 'https://kite.kagi.com/api'
_KAGI_HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'KagiNews/1.1.0 (Android)',
    '-acx-global-context': '{"platform":"android","app_version":"1.1.0","build":"84","client":"com.kagi.news"}',
}
_KAGI_DEFAULT_CATS = ['science', 'tech', 'ai']
_KAGI_GRADIENTS = {
    'science': 'linear-gradient(160deg,#0f2027,#203a43,#2c5364)',
    'tech':    'linear-gradient(160deg,#0f0c29,#302b63,#24243e)',
    'ai':      'linear-gradient(160deg,#0d0221,#1b1b2f,#3a1a6e)',
}


def _kagi_get(path, params=None):
    url = f'{_KAGI_API_BASE}{path}'
    if params:
        url += '?' + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers=_KAGI_HEADERS)
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read())


@cached(ttl=1800)
def _fetch(categories_key):
    categories = categories_key.split(',') if categories_key else _KAGI_DEFAULT_CATS
    resp = _kagi_get('/batches/latest/categories', {'lang': 'default'})
    batch_id = resp.get('batchId', '')
    cat_list = resp.get('categories', [])
    cat_map = {c['categoryId']: c['id'] for c in cat_list}

    stories = []
    needs_og = []

    for cat_id in categories:
        uuid = cat_map.get(cat_id)
        if not uuid:
            print(f'[kagi] category {cat_id!r} not found in batch')
            continue
        try:
            data = _kagi_get(f'/batches/{batch_id}/categories/{uuid}/stories',
                             {'limit': 5, 'lang': 'default'})
            for s in data.get('stories', []):
                img = ((s.get('primary_image') or {}).get('url') or
                       (s.get('secondary_image') or {}).get('url') or '')
                if 'kagiproxy.com' in img:
                    img = ''
                sources = [d['name'] for d in (s.get('domains') or [])[:3]]
                url = next((a['link'] for a in (s.get('articles') or []) if a.get('link')), '')
                stories.append({
                    'title':    s.get('title', '').strip(),
                    'summary':  s.get('short_summary', '').strip(),
                    'image':    img,
                    'gradient': _KAGI_GRADIENTS.get(cat_id, _KAGI_GRADIENTS['tech']),
                    'category': cat_id.upper(),
                    'sources':  sources,
                    'url':      url,
                })
                if not img:
                    needs_og.append((len(stories) - 1, s.get('articles') or []))
        except Exception as e:
            print(f'[kagi] stories for {cat_id} failed: {e}')

    if needs_og:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(fetch_og_image, arts): idx for idx, arts in needs_og}
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    stories[idx]['image'] = fut.result() or ''
                except Exception:
                    pass

    return stories


@bp.route('/kagi_stories')
def api_kagi_stories():
    raw = request.args.get('categories', '')
    cats = ','.join(sorted(c.strip() for c in raw.split(',') if c.strip())) if raw else ''
    try:
        return jsonify(_fetch(cats))
    except Exception as e:
        print(f'[kagi] fetch failed: {e}')
        return jsonify([]), 502
