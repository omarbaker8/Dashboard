import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Blueprint, jsonify
from server.services.cache import cached

bp = Blueprint('widget_ap_card', __name__, url_prefix='/api')

_SCRAPE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}


def _fetch_article(url):
    try:
        r = requests.get(url, headers=_SCRAPE_HEADERS, timeout=6)
        soup = BeautifulSoup(r.text, 'html.parser')
        og_img = soup.select_one('meta[property="og:image"]')
        image = og_img.get('content', '') if og_img else ''
        sec = soup.select_one('meta[property="article:section"]')
        category = sec.get('content', '') if sec else ''
        h1 = soup.find('h1')
        headline = h1.get_text(strip=True) if h1 else ''
        return image, category, headline
    except Exception:
        return '', '', ''


@cached(ttl=300)
def _fetch():
    try:
        r = requests.get('https://apnews.com/', headers=_SCRAPE_HEADERS, timeout=8)
        soup = BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f'[ap_cards] homepage failed: {e}')
        return []

    candidates = []
    for item in soup.select('bsp-scroll-shade.PageList-items .PageList-items-item'):
        url = item.get('data-page-url', '')
        title_el = item.select_one('.PagePromoContentIcons-text')
        title = title_el.get_text(strip=True) if title_el else ''
        if not (title and url):
            continue
        is_live = bool(item.select_one('.PageListTrending-LiveTag'))
        candidates.append({'title': title, 'url': url, 'isLive': is_live, 'image': '', 'category': ''})
        if len(candidates) >= 8:
            break

    if not candidates:
        return []

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_map = {executor.submit(_fetch_article, c['url']): i for i, c in enumerate(candidates)}
        for future in as_completed(future_map):
            i = future_map[future]
            image, category, headline = future.result()
            candidates[i]['image'] = image
            candidates[i]['category'] = category
            if headline:
                candidates[i]['headline'] = headline
    return candidates


@bp.route('/ap_cards')
def api_ap_cards():
    try:
        return jsonify(_fetch())
    except Exception as e:
        print(f"[ap_cards] failed: {e}")
        return jsonify([]), 502
