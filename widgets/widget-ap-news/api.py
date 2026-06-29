import json
import re
import calendar
import urllib.request
from datetime import datetime
from flask import Blueprint, request, jsonify
from server.services.cache import cached

bp = Blueprint('widget_ap_news', __name__, url_prefix='/api')

_AP_GRAPHQL_URL = 'https://apnews.com/graphql/delivery/ap/v1'
_AP_BASE_URL    = 'https://apnews.com'
_AP_HEADERS = {
    'User-Agent':   'mnn.Android',
    'Content-Type': 'application/json',
    'Accept':       'application/json',
}
_AP_QUERY_HUB = (
    'query Q($path:String,$adLite:Boolean){'
    'Screen(path:$path,adLite:$adLite){'
    'main{__typename'
    '...on ColumnContainer{columns{__typename'
    '...on PageListModule{items{__typename'
    '...on PagePromo{title url category liveEvent publishDate}'
    '}}}}}}'
    '}'
)
_AP_QUERY_WEB = (
    'query WebQuery($path:String,$adLite:Boolean){'
    'Web(path:$path,adLite:$adLite){headline category}'
    '}'
)
_AP_DATE_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
_AP_LIVE_RE = re.compile(r'apnews\.com(/live/[a-z0-9-]+)')
_AP_HUB_SECTIONS = [
    ('top-news',     '/hub/apf-topnews'),
    ('technology',   '/hub/artificial-intelligence'),
    ('science',      '/hub/space'),
    ('politics',     '/hub/politics'),
    ('sports',       '/hub/sports'),
    ('health',       '/hub/health'),
    ('entertainment','/hub/entertainment'),
    ('business',     '/hub/business'),
    ('us-news',      '/hub/us-news'),
]
_AP_CAT_MAP = {
    'World News': 'world', 'U.S. News': 'us-news', 'Politics': 'politics',
    'Sports': 'sports', 'Science': 'science', 'Health': 'health',
    'Entertainment': 'entertainment', 'Business': 'business',
}


def _parse_ap_date(s):
    try:
        dt = datetime.strptime(s.strip(), '%B %d, %Y %I:%M %p')
        return int(calendar.timegm(dt.timetuple()))
    except Exception:
        return None


def _parse_iso_date(s):
    try:
        s = re.sub(r'\.\d+', '', s).rstrip('Z')
        if '+' in s[10:]:
            s = s[:s.rfind('+')]
        dt = datetime.strptime(s, '%Y-%m-%dT%H:%M:%S')
        return int(calendar.timegm(dt.timetuple()))
    except Exception:
        return None


def _ap_graphql(query, variables):
    payload = json.dumps({'query': query, 'variables': variables}).encode('utf-8')
    req = urllib.request.Request(_AP_GRAPHQL_URL, data=payload, headers=_AP_HEADERS, method='POST')
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())


def _ap_live_blog_ts(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'text/html'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            html = resp.read(131072).decode('utf-8', errors='replace')
        m = _AP_DATE_RE.search(html)
        if m:
            return _parse_iso_date(m.group(1))
    except Exception:
        pass
    return None


def _ap_fetch_live_blogs():
    req = urllib.request.Request(_AP_BASE_URL, headers={'User-Agent': 'mnn.Android', 'Accept': 'text/html'})
    with urllib.request.urlopen(req, timeout=8) as resp:
        html = resp.read().decode('utf-8', errors='replace')
    live_paths = list(dict.fromkeys(_AP_LIVE_RE.findall(html)))
    results = []
    for path in live_paths[:6]:
        try:
            data = _ap_graphql(_AP_QUERY_WEB, {'path': path, 'adLite': True})
            web = (data.get('data') or {}).get('Web') or {}
            if web.get('headline'):
                url = f'{_AP_BASE_URL}{path}'
                item = {'title': web['headline'], 'url': url, 'isLive': True}
                pts = _ap_live_blog_ts(url)
                if pts:
                    item['pub_ts'] = pts
                results.append(item)
        except Exception as e:
            print(f'[ap_news] live blog {path} failed: {e}')
    return results


def _ap_fetch_hub(path):
    data = _ap_graphql(_AP_QUERY_HUB, {'path': path, 'adLite': True})
    items = []
    screen = (data.get('data') or {}).get('Screen') or {}
    for block in (screen.get('main') or []):
        for col in (block.get('columns') or []):
            for item in (col.get('items') or []):
                if item.get('__typename') == 'PagePromo' and item.get('title'):
                    items.append(item)
    return items


@cached(ttl=300)
def _fetch():
    seen_urls = set()
    all_keys = ['live', 'world', 'technology', 'science', 'politics',
                'sports', 'health', 'entertainment', 'business', 'us-news', 'top']
    buckets = {k: [] for k in all_keys}

    try:
        for lb in _ap_fetch_live_blogs():
            url = lb['url']
            if url not in seen_urls:
                seen_urls.add(url)
                buckets['live'].append(lb)
    except Exception as e:
        print(f'[ap_news] live blogs failed: {e}')

    for key, path in _AP_HUB_SECTIONS:
        try:
            raw = _ap_fetch_hub(path)
        except Exception as e:
            print(f'[ap_news] hub {key} failed: {e}')
            raw = []
        for item in raw:
            url = item.get('url', '')
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            a = {'title': item['title'].strip(), 'url': url, 'isLive': False}
            pd = item.get('publishDate')
            if pd:
                pts = _parse_ap_date(pd)
                if pts:
                    a['pub_ts'] = pts
            cat = item.get('category') or ''
            if item.get('liveEvent'):
                a['isLive'] = True
                buckets['live'].append(a)
            elif key == 'top-news':
                buckets[_AP_CAT_MAP.get(cat, 'top')].append(a)
            else:
                buckets[key].append(a)

    _GROUP_ORDER = [
        ('live',          'Live',          4),
        ('world',         'World News',    4),
        ('us-news',       'U.S. News',     3),
        ('politics',      'Politics',      3),
        ('technology',    'Technology',    3),
        ('science',       'Science',       3),
        ('business',      'Business',      3),
        ('health',        'Health',        3),
        ('sports',        'Sports',        3),
        ('entertainment', 'Entertainment', 3),
        ('top',           'Top Stories',   4),
    ]
    return [
        {'label': label, 'items': buckets[key][:limit]}
        for key, label, limit in _GROUP_ORDER
        if buckets[key]
    ]


@bp.route('/ap_news')
def api_ap_news():
    try:
        return jsonify(_fetch())
    except Exception as e:
        print(f"[ap_news] failed: {e}")
        return jsonify([]), 502
