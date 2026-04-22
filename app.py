import os
import json
import re
import time
import threading
import urllib.request
import urllib.parse
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, abort, make_response

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from PIL import Image
from io import BytesIO
from db import (get_device, create_device, list_devices, get_device_config,
                save_device_config, get_device_widgets, save_device_widget,
                init_device_widgets, DEFAULT_CONFIG, get_preset_layout,
                add_device_widget, remove_device_widget, get_device_widget_ids)

app = Flask(__name__)

WIDGETS_DIR = 'widgets'
WALLPAPERS_DIR = os.path.join('static', 'wallpapers')
THUMBS_DIR = os.path.join(WALLPAPERS_DIR, '.thumbs')
THUMB_SIZE = (280, 175)
ALLOWED_IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg')
AERIALS_DIR = os.path.join('static', 'aerials')

os.makedirs(WIDGETS_DIR, exist_ok=True)
os.makedirs(AERIALS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Aerial catalog + download state
# ---------------------------------------------------------------------------
_AERIAL_CATALOG = []
_aerial_downloads = {}  # {id: {'status': 'downloading'|'ready'|'error', 'progress': 0-100}}

try:
    with open('aerial_catalog.json') as _f:
        _AERIAL_CATALOG = json.load(_f)
    print(f'[aerials] loaded {len(_AERIAL_CATALOG)} videos')
except Exception as _e:
    print(f'[aerials] catalog load failed: {_e}')


# ---------------------------------------------------------------------------
# Widget I/O — base widget definitions from disk (templates)
# ---------------------------------------------------------------------------

def get_base_widgets():
    """Read widget definitions from disk. These are the base templates."""
    widgets = []
    for item in sorted(os.listdir(WIDGETS_DIR)):
        item_path = os.path.join(WIDGETS_DIR, item)
        if not os.path.isdir(item_path):
            continue
        filepath = os.path.join(item_path, 'data.js')
        if not os.path.exists(filepath):
            continue
        with open(filepath, 'r') as f:
            content = f.read().strip()
        if content.startswith('module.exports = '):
            content = content[len('module.exports = '):]
        if content.endswith(';'):
            content = content[:-1]
        try:
            widgets.append(json.loads(content))
        except json.JSONDecodeError as e:
            print(f"[widget-load] skipping {filepath}: {e}")
    return sorted(widgets, key=lambda x: x.get('id', ''))


def save_base_widget(widget):
    """Save widget definition to disk (base template)."""
    widget_dir = os.path.join(WIDGETS_DIR, widget['id'])
    os.makedirs(widget_dir, exist_ok=True)
    filepath = os.path.join(widget_dir, 'data.js')
    with open(filepath, 'w') as f:
        f.write(f"module.exports = {json.dumps(widget, indent=4)};")


# ---------------------------------------------------------------------------
# Device-aware helpers
# ---------------------------------------------------------------------------

def current_device_id():
    """Get device_id from cookie, or None if not set."""
    return request.cookies.get('device_id')


def require_device():
    """Return device dict or None. If None, caller should redirect to setup."""
    did = current_device_id()
    if not did:
        return None
    return get_device(did)


def get_widgets_for_device(device_id):
    """Get widgets with per-device overrides applied."""
    return get_device_widgets(device_id, get_base_widgets())


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    if not require_device():
        return redirect(url_for('setup'))
    return redirect(url_for('dashboard'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        device_type = request.form.get('device_type', 'laptop')
        if device_type not in ('laptop', 'tablet'):
            device_type = 'laptop'
        # Step 1: device type chosen → forward to widget picker
        return redirect(url_for('setup_widgets', type=device_type))

    devices = list_devices()
    return render_template('setup.html', devices=devices)


@app.route('/setup/widgets', methods=['GET', 'POST'])
def setup_widgets():
    device_type = request.args.get('type') or request.form.get('device_type', 'laptop')
    if device_type not in ('laptop', 'tablet'):
        device_type = 'laptop'

    base_widgets = get_base_widgets()
    base_by_id = {bw['id']: bw for bw in base_widgets}
    preset_ids = [entry[0] for entry in get_preset_layout(device_type)
                  if entry[0] in base_by_id]

    if request.method == 'POST':
        selected = set(request.form.getlist('widgets'))
        # Default location from picker
        d_lat = request.form.get('default_lat', '').strip()
        d_lng = request.form.get('default_lng', '').strip()
        d_city = request.form.get('default_city', '').strip()
        d_tz = request.form.get('default_timezone', '').strip()
        lat = float(d_lat) if d_lat else None
        lng = float(d_lng) if d_lng else None

        device_id, name = create_device(device_type)
        init_device_widgets(device_id, device_type, base_widgets,
                            selected_ids=selected,
                            default_lat=lat, default_lng=lng,
                            default_city=d_city or None, default_timezone=d_tz or None)
        cfg = dict(DEFAULT_CONFIG)
        if lat is not None:
            cfg['default_lat'] = lat
            cfg['default_lng'] = lng
            cfg['default_city'] = d_city
            cfg['default_timezone'] = d_tz
        save_device_config(device_id, cfg)

        resp = make_response(redirect(url_for('dashboard')))
        resp.set_cookie('device_id', device_id, max_age=60*60*24*365*5, httponly=True, samesite='Lax')
        return resp

    # All preset widgets pre-checked by default
    return render_template('setup_widgets.html',
                           device_type=device_type,
                           widgets=[base_by_id[wid] for wid in preset_ids],
                           preselected=set(preset_ids))


@app.route('/switch/<device_id>')
def switch_device(device_id):
    """Switch to an existing device."""
    device = get_device(device_id)
    if not device:
        return redirect(url_for('setup'))
    resp = make_response(redirect(url_for('dashboard')))
    resp.set_cookie('device_id', device_id, max_age=60*60*24*365*5, httponly=True, samesite='Lax')
    return resp


@app.route('/dashboard')
def dashboard():
    device = require_device()
    if not device:
        return redirect(url_for('setup'))
    config = get_device_config(device['id'])
    widgets = get_widgets_for_device(device['id'])
    return render_template('dashboard.html', widgets=widgets, config=config, device=device)


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    device = require_device()
    if not device:
        return redirect(url_for('setup'))

    config = get_device_config(device['id'])

    if request.method == 'POST':
        action = request.form.get('action')
        is_ajax = (request.headers.get('X-Requested-With') == 'fetch'
                   or 'application/json' in (request.headers.get('Accept') or ''))

        if action == 'update_widget':
            widget_id = request.form.get('id', '').strip()
            new_css = request.form.get('css', '').strip()
            if widget_id and new_css:
                widgets = get_widgets_for_device(device['id'])
                for w in widgets:
                    if w['id'] == widget_id:
                        w['css'] = new_css
                        for key in ('lat', 'lng'):
                            val = request.form.get(key)
                            if val is not None:
                                try:
                                    w[key] = float(val)
                                except ValueError:
                                    pass
                        for key in ('timezone', 'city'):
                            val = request.form.get(key)
                            if val is not None:
                                w[key] = val.strip()
                        ri = request.form.get('refresh_interval')
                        if ri is not None:
                            try:
                                w['refresh_interval'] = int(ri)
                            except ValueError:
                                pass
                        hts = request.form.get('hours_to_show')
                        if hts is not None:
                            try:
                                w['hours_to_show'] = max(1, min(12, int(hts)))
                            except ValueError:
                                pass
                        _lv = request.form.get('levels')
                        if _lv is not None:
                            try:
                                w['levels'] = max(1, min(10, int(_lv)))
                            except ValueError:
                                pass
                        _st = request.form.get('stroke')
                        if _st is not None:
                            try:
                                w['stroke'] = max(0.0, min(20.0, float(_st)))
                            except ValueError:
                                pass
                        _sr = request.form.get('split_ratio')
                        if _sr is not None:
                            try:
                                w['split_ratio'] = max(0.0, min(1.0, float(_sr)))
                            except ValueError:
                                pass
                        _kc = request.form.get('kagi_categories')
                        if _kc is not None:
                            cats = [c.strip() for c in _kc.split(',') if c.strip()]
                            if cats:
                                w['categories'] = cats
                        save_device_widget(device['id'], w)
                        break
            if is_ajax:
                return jsonify({"status": "ok", "action": action, "id": widget_id})

        elif action == 'update_default_location':
            d_lat = request.form.get('default_lat', '').strip()
            d_lng = request.form.get('default_lng', '').strip()
            d_city = request.form.get('default_city', '').strip()
            d_tz = request.form.get('default_timezone', '').strip()
            if d_lat and d_lng:
                try:
                    config['default_lat'] = float(d_lat)
                    config['default_lng'] = float(d_lng)
                    config['default_city'] = d_city
                    config['default_timezone'] = d_tz
                    save_device_config(device['id'], config)
                except ValueError:
                    pass
            if is_ajax:
                return jsonify({"status": "ok", "action": action})

        elif action == 'update_background':
            bg_css = request.form.get('background_css', '').strip()
            if bg_css:
                config['background'] = bg_css
                config['bg_video'] = ''  # clear video when static wallpaper applied
            bg_blur = request.form.get('bg_blur', '0')
            bg_dim = request.form.get('bg_dim', '0')
            config['bg_blur'] = int(bg_blur) if bg_blur.isdigit() else 0
            config['bg_dim'] = int(bg_dim) if bg_dim.isdigit() else 0
            # Live wallpaper (aerial video)
            bg_video = request.form.get('bg_video', None)
            if bg_video is not None:
                config['bg_video'] = bg_video.strip()
                if config['bg_video']:
                    config['background'] = 'transparent'
            save_device_config(device['id'], config)
            if is_ajax:
                return jsonify({"status": "ok", "action": action, "config": config})

        elif action == 'remove_widget':
            widget_id = request.form.get('id', '').strip()
            if widget_id:
                remove_device_widget(device['id'], widget_id)
            if is_ajax:
                return jsonify({"status": "ok", "action": action, "id": widget_id})

        elif action == 'add_widget':
            widget_id = request.form.get('id', '').strip()
            if widget_id:
                base_by_id = {bw['id']: bw for bw in get_base_widgets()}
                if widget_id in base_by_id:
                    d_lat = config.get('default_lat')
                    d_lng = config.get('default_lng')
                    d_city = config.get('default_city', '')
                    d_tz = config.get('default_timezone', '')
                    add_device_widget(device['id'], device['type'], widget_id,
                                      base_widget=base_by_id[widget_id],
                                      default_lat=d_lat if isinstance(d_lat, (int, float)) else None,
                                      default_lng=d_lng if isinstance(d_lng, (int, float)) else None,
                                      default_city=d_city or None,
                                      default_timezone=d_tz or None)
            if is_ajax:
                return jsonify({"status": "ok", "action": action, "id": widget_id})

        return redirect(url_for('settings'))

    widgets = get_widgets_for_device(device['id'])
    # Build available widgets list (all base widgets + flag for currently active)
    base_widgets = get_base_widgets()
    active_ids = get_device_widget_ids(device['id'])
    available_widgets = [{'id': bw['id'], 'active': bw['id'] in active_ids}
                         for bw in base_widgets]
    return render_template('settings.html', widgets=widgets, config=config,
                           device=device, available_widgets=available_widgets)


# ---------------------------------------------------------------------------
# Fonts — widgets reference /fonts/SFNS.ttf etc.
# ---------------------------------------------------------------------------

FONTS_DIR = os.path.join('static', 'fonts')


@app.route('/fonts/<path:filename>')
def serve_font(filename):
    safe_name = os.path.basename(filename)
    if safe_name != filename or '..' in filename:
        abort(400)
    path = os.path.join(FONTS_DIR, safe_name)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path)


# ---------------------------------------------------------------------------
# API: Wallpapers
# ---------------------------------------------------------------------------

@app.route('/api/wallpapers')
def api_wallpapers():
    if not os.path.isdir(WALLPAPERS_DIR):
        return jsonify([])
    files = []
    for f in sorted(os.listdir(WALLPAPERS_DIR)):
        if f.lower().endswith(ALLOWED_IMAGE_EXT):
            files.append({
                'name': os.path.splitext(f)[0],
                'file': f,
                'url': f'/static/wallpapers/{f}',
                'thumb': f'/api/thumb/{f}'
            })
    return jsonify(files)


# ---------------------------------------------------------------------------
# API: Aerial (Live Wallpapers)
# ---------------------------------------------------------------------------

@app.route('/api/aerials')
def api_aerials():
    result = []
    for item in _AERIAL_CATALOG:
        vid_id = item['id']
        local_path = os.path.join(AERIALS_DIR, vid_id + '.mov')
        if os.path.exists(local_path):
            status = 'ready'
            progress = 100
        elif vid_id in _aerial_downloads:
            status = _aerial_downloads[vid_id]['status']
            progress = _aerial_downloads[vid_id]['progress']
        else:
            status = 'idle'
            progress = 0
        result.append({
            'id': vid_id,
            'name': item['name'],
            'status': status,
            'progress': progress,
        })
    return jsonify(result)


@app.route('/api/aerials/download', methods=['POST'])
def api_aerials_download():
    data = request.get_json(silent=True) or {}
    vid_id = (data.get('id') or request.form.get('id', '')).strip()
    item = next((a for a in _AERIAL_CATALOG if a['id'] == vid_id), None)
    if not item:
        return jsonify({'error': 'not found'}), 404

    local_path = os.path.join(AERIALS_DIR, vid_id + '.mov')
    if os.path.exists(local_path):
        _aerial_downloads[vid_id] = {'status': 'ready', 'progress': 100}
        return jsonify({'status': 'ready'})

    if _aerial_downloads.get(vid_id, {}).get('status') == 'downloading':
        return jsonify({'status': 'downloading'})

    url = item.get('url_1080_h264') or item.get('url_1080_sdr', '')
    _aerial_downloads[vid_id] = {'status': 'downloading', 'progress': 0}

    def do_download():
        try:
            def reporthook(count, block_size, total_size):
                if total_size > 0:
                    _aerial_downloads[vid_id]['progress'] = min(99, int(count * block_size * 100 / total_size))
            urllib.request.urlretrieve(url, local_path, reporthook)
            _aerial_downloads[vid_id] = {'status': 'ready', 'progress': 100}
            print(f'[aerials] downloaded {vid_id} ({item["name"]})')
        except Exception as e:
            _aerial_downloads[vid_id] = {'status': 'error', 'progress': 0}
            if os.path.exists(local_path):
                os.remove(local_path)
            print(f'[aerials] download failed {vid_id}: {e}')

    threading.Thread(target=do_download, daemon=True).start()
    return jsonify({'status': 'downloading'})


@app.route('/api/aerials/status')
def api_aerials_status():
    vid_id = request.args.get('id', '').strip()
    local_path = os.path.join(AERIALS_DIR, vid_id + '.mov')
    if os.path.exists(local_path):
        status, progress = 'ready', 100
    elif vid_id in _aerial_downloads:
        status = _aerial_downloads[vid_id]['status']
        progress = _aerial_downloads[vid_id]['progress']
    else:
        status, progress = 'idle', 0
    return jsonify({
        'id': vid_id,
        'status': status,
        'progress': progress,
        'local_url': f'/static/aerials/{vid_id}.mov' if status == 'ready' else None,
    })


@app.route('/api/aerials/refresh', methods=['POST'])
def api_aerials_refresh():
    global _AERIAL_CATALOG
    try:
        def fetch_json(url):
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())

        videos_data = fetch_json(
            'https://raw.githubusercontent.com/aabytt/custom-screensaver-aerial/refs/heads/main/assets/videos.json'
        )
        locale_data = fetch_json(
            'https://raw.githubusercontent.com/aabytt/custom-screensaver-aerial/refs/heads/main/assets/locales/en-GB.json'
        )

        catalog = []
        for asset in videos_data.get('assets', []):
            raw_key = asset.get('localizedNameKey', '')
            lookup_key = raw_key.replace('_NAME', '')
            name = (locale_data.get(raw_key) or locale_data.get(lookup_key)
                    or raw_key.replace('_NAME', '').replace('_', ' ').title())
            catalog.append({
                'id': asset['id'],
                'name': name,
                'url_1080_h264': asset.get('url-1080-H264', ''),
                'url_1080_sdr':  asset.get('url-1080-SDR', ''),
            })

        with open('aerial_catalog.json', 'w') as f:
            json.dump(catalog, f, indent=2)
        _AERIAL_CATALOG = catalog
        print(f'[aerials] refreshed catalog: {len(catalog)} videos')
        return jsonify({'status': 'ok', 'count': len(catalog)})
    except Exception as e:
        print(f'[aerials] refresh failed: {e}')
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/aerials/delete', methods=['POST'])
def api_aerials_delete():
    data = request.get_json(silent=True) or {}
    vid_id = (data.get('id') or request.form.get('id', '')).strip()
    local_path = os.path.join(AERIALS_DIR, vid_id + '.mov')
    if os.path.exists(local_path):
        os.remove(local_path)
    _aerial_downloads.pop(vid_id, None)
    return jsonify({'status': 'ok'})


@app.route('/api/thumb/<path:filename>')
def api_thumb(filename):
    safe_name = os.path.basename(filename)
    if safe_name != filename or '..' in filename:
        abort(400)

    src = os.path.join(WALLPAPERS_DIR, safe_name)
    if not os.path.isfile(src):
        abort(404)

    os.makedirs(THUMBS_DIR, exist_ok=True)
    thumb_name = os.path.splitext(safe_name)[0] + '.jpg'
    thumb_path = os.path.join(THUMBS_DIR, thumb_name)

    if os.path.isfile(thumb_path) and os.path.getmtime(thumb_path) >= os.path.getmtime(src):
        return send_file(thumb_path, mimetype='image/jpeg')

    try:
        img = Image.open(src)
        img.thumbnail(THUMB_SIZE, Image.LANCZOS)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=70, optimize=True)
        img.save(thumb_path, format='JPEG', quality=70, optimize=True)
        buf.seek(0)
        return send_file(buf, mimetype='image/jpeg')
    except Exception as e:
        print(f"[thumb] error for {safe_name}: {e}")
        abort(500)


# ---------------------------------------------------------------------------
# API: Layout persistence (now per-device)
# ---------------------------------------------------------------------------

@app.route('/api/update_layout', methods=['POST'])
def update_layout():
    device = require_device()
    if not device:
        return jsonify({"status": "error", "message": "no device"})

    changes = request.json
    if not changes:
        return jsonify({"status": "error", "message": "no data"})

    widgets = get_widgets_for_device(device['id'])
    widget_map = {w['id']: w for w in widgets}

    for item in changes:
        wid = item.get('id')
        if wid not in widget_map:
            continue
        w = widget_map[wid]
        for key in ('x', 'y', 'w', 'h'):
            val = item.get(key)
            if val is not None:
                w[key] = val
        save_device_widget(device['id'], w)

    return jsonify({"status": "success"})


# ---------------------------------------------------------------------------
# API: BBC News
# ---------------------------------------------------------------------------

BBC_LIVE_URL = 'https://www.bbc.com/live/news'
_bbc_cache = {'ts': 0, 'items': []}
_BBC_TTL = 300
_BBC_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', re.DOTALL)


def fetch_bbc_news():
    now = time.time()
    if _bbc_cache['items'] and (now - _bbc_cache['ts']) < _BBC_TTL:
        return _bbc_cache['items']

    try:
        req = urllib.request.Request(BBC_LIVE_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode('utf-8', errors='replace')

        m = _BBC_NEXT_DATA_RE.search(html)
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

        if items:
            _bbc_cache['items'] = items
            _bbc_cache['ts'] = now
        return items
    except Exception as e:
        print(f"[bbc] fetch failed: {e}")
        return _bbc_cache['items']


@app.route('/api/bbc_news')
def api_bbc_news():
    return jsonify(fetch_bbc_news())


# ---------------------------------------------------------------------------
# API: AP News
# ---------------------------------------------------------------------------

AP_GRAPHQL_URL = 'https://apnews.com/graphql/delivery/ap/v1'
AP_BASE_URL    = 'https://apnews.com'
_ap_cache = {'ts': 0, 'groups': []}
_AP_TTL = 300

_AP_HEADERS = {
    'User-Agent':   'mnn.Android',
    'Content-Type': 'application/json',
    'Accept':       'application/json',
}

# Hub query — returns PagePromo items with category + liveEvent flag
_AP_QUERY_HUB = (
    'query Q($path:String,$adLite:Boolean){'
    'Screen(path:$path,adLite:$adLite){'
    'main{__typename'
    '...on ColumnContainer{columns{__typename'
    '...on PageListModule{items{__typename'
    '...on PagePromo{title url category liveEvent}'
    '}}}}}}'
    '}'
)

# WebQuery — used for /live/ paths discovered via homepage scrape (same as ap.py)
_AP_QUERY_WEB = (
    'query WebQuery($path:String,$adLite:Boolean){'
    'Web(path:$path,adLite:$adLite){headline category}'
    '}'
)

_AP_LIVE_RE = re.compile(r'apnews\.com(/live/[a-z0-9-]+)')

# Only /hub/apf-topnews works from the old APK paths.
# Technology and Science use the real hub paths discovered from the homepage.
# Category values actually returned by AP: "World News", "U.S. News", "Business",
# "Politics", "Sports", "Science", "Health", "Entertainment" — no "Technology" category.
# AI/tech articles come back as "Business", so we use the /hub/artificial-intelligence
# path and bucket by source hub, not category.
_AP_HUB_SECTIONS = [
    ('top-news',   '/hub/apf-topnews'),
    ('technology', '/hub/artificial-intelligence'),
    ('science',    '/hub/space'),
]


def _ap_graphql(query, variables):
    payload = json.dumps({'query': query, 'variables': variables}).encode('utf-8')
    req = urllib.request.Request(AP_GRAPHQL_URL, data=payload, headers=_AP_HEADERS, method='POST')
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())


def _ap_fetch_live_blogs():
    """Scrape AP homepage for /live/ paths, query each via WebQuery — mirrors ap.py get_live_blogs()."""
    req = urllib.request.Request(AP_BASE_URL, headers={'User-Agent': 'mnn.Android', 'Accept': 'text/html'})
    with urllib.request.urlopen(req, timeout=8) as resp:
        html = resp.read().decode('utf-8', errors='replace')
    live_paths = list(dict.fromkeys(_AP_LIVE_RE.findall(html)))
    results = []
    for path in live_paths[:6]:
        try:
            data = _ap_graphql(_AP_QUERY_WEB, {'path': path, 'adLite': True})
            web = (data.get('data') or {}).get('Web') or {}
            if web.get('headline'):
                results.append({'title': web['headline'], 'url': f'{AP_BASE_URL}{path}', 'isLive': True})
        except Exception as e:
            print(f'[ap_news] live blog {path} failed: {e}')
    return results


def _ap_fetch_hub(path):
    """Fetch one hub section. Returns list of raw PagePromo dicts."""
    data = _ap_graphql(_AP_QUERY_HUB, {'path': path, 'adLite': True})
    items = []
    screen = (data.get('data') or {}).get('Screen') or {}
    for block in (screen.get('main') or []):
        for col in (block.get('columns') or []):
            for item in (col.get('items') or []):
                if item.get('__typename') == 'PagePromo' and item.get('title'):
                    items.append(item)
    return items


def fetch_ap_news():
    now = time.time()
    if _ap_cache['groups'] and (now - _ap_cache['ts']) < _AP_TTL:
        return _ap_cache['groups']

    seen_urls = set()
    buckets = {'live': [], 'world': [], 'technology': [], 'science': [], 'top': []}

    # 1. Live blogs via homepage scrape (the source the original script uses)
    try:
        for lb in _ap_fetch_live_blogs():
            url = lb['url']
            if url not in seen_urls:
                seen_urls.add(url)
                buckets['live'].append(lb)
    except Exception as e:
        print(f'[ap_news] live blogs failed: {e}')

    # 2. Hub sections
    # top-news: route by category ("World News" → world, liveEvent → live, rest → top)
    # technology hub (/hub/artificial-intelligence): all articles → technology (no "Technology" category exists)
    # science hub (/hub/space): all articles → science (category is "Science")
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
            cat = item.get('category') or ''
            if item.get('liveEvent'):
                a['isLive'] = True
                buckets['live'].append(a)
            elif key == 'technology':
                buckets['technology'].append(a)
            elif key == 'science':
                buckets['science'].append(a)
            elif cat == 'World News':
                buckets['world'].append(a)
            else:
                buckets['top'].append(a)

    groups = []
    if buckets['live']:
        groups.append({'label': 'Live',        'items': buckets['live'][:4]})
    if buckets['world']:
        groups.append({'label': 'World News',  'items': buckets['world'][:4]})
    if buckets['technology']:
        groups.append({'label': 'Technology',  'items': buckets['technology'][:3]})
    if buckets['science']:
        groups.append({'label': 'Science',     'items': buckets['science'][:3]})
    if buckets['top']:
        groups.append({'label': 'Top Stories', 'items': buckets['top'][:4]})

    if groups:
        _ap_cache['groups'] = groups
        _ap_cache['ts'] = now
    return groups


@app.route('/api/ap_news')
def api_ap_news():
    return jsonify(fetch_ap_news())


# ---------------------------------------------------------------------------
# API: Google Weather (wind) — keyed by lat/lng, cached 10 minutes per location
# ---------------------------------------------------------------------------

GOOGLE_WEATHER_URL = 'https://weather.googleapis.com/v1/currentConditions:lookup'
_wind_cache = {}  # {(lat,lng): {'ts': ..., 'data': ...}}


def _google_weather_fetch(url_base, params_base):
    """Try GOOGLE_WEATHER_KEY then GOOGLE_WEATHER_KEY_2 on any failure."""
    keys = [k for k in [os.getenv('GOOGLE_WEATHER_KEY'), os.getenv('GOOGLE_WEATHER_KEY_2')] if k]
    if not keys:
        raise ValueError("no Google Weather API key configured")
    last_exc = None
    for key in keys:
        try:
            params = urllib.parse.urlencode({**params_base, 'key': key})
            req = urllib.request.Request(f'{url_base}?{params}')
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.loads(r.read())
        except Exception as e:
            print(f"[google_weather] key failed ({key[:8]}…): {e}")
            last_exc = e
    raise last_exc
_WIND_TTL = 600  # 10 minutes


@app.route('/api/google_wind')
def api_google_wind():
    if not (os.getenv('GOOGLE_WEATHER_KEY') or os.getenv('GOOGLE_WEATHER_KEY_2')):
        return jsonify({"error": "missing API key"}), 503

    try:
        lat = float(request.args.get('lat', '53.3498'))
        lng = float(request.args.get('lng', '-6.2603'))
    except ValueError:
        return jsonify({"error": "invalid lat/lng"}), 400

    cache_key = (round(lat, 3), round(lng, 3))
    now = time.time()
    cached = _wind_cache.get(cache_key)
    if cached and (now - cached['ts']) < _WIND_TTL:
        return jsonify(cached['data'])

    try:
        full = _google_weather_fetch(GOOGLE_WEATHER_URL, {
            'location.latitude': lat,
            'location.longitude': lng,
        })
        wind = full.get('wind', {})
        result = {
            'speed': (wind.get('speed') or {}).get('value'),
            'gust': (wind.get('gust') or {}).get('value'),
            'direction': (wind.get('direction') or {}).get('degrees'),
            'cardinal': (wind.get('direction') or {}).get('cardinal', ''),
            'unit': (wind.get('speed') or {}).get('unit', 'KILOMETERS_PER_HOUR'),
        }
        _wind_cache[cache_key] = {'ts': now, 'data': result}
        return jsonify(result)
    except Exception as e:
        print(f"[google_wind] fetch failed: {e}")
        if cached:
            return jsonify(cached['data'])
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# API: Google Weather (alerts) — keyed by lat/lng, cached 5 minutes per location
# ---------------------------------------------------------------------------

GOOGLE_ALERTS_URL = 'https://weather.googleapis.com/v1/publicAlerts:lookup'
_alerts_cache = {}  # {(lat,lng,lang): {'ts': ..., 'data': ...}}
_ALERTS_TTL = 300  # 5 minutes


@app.route('/api/google_weather_alerts')
def api_google_weather_alerts():
    if not (os.getenv('GOOGLE_WEATHER_KEY') or os.getenv('GOOGLE_WEATHER_KEY_2')):
        return jsonify({"error": "missing API key"}), 503

    try:
        lat = float(request.args.get('lat', '53.3498'))
        lng = float(request.args.get('lng', '-6.2603'))
    except ValueError:
        return jsonify({"error": "invalid lat/lng"}), 400
    lang = request.args.get('lang', 'en')

    cache_key = (round(lat, 3), round(lng, 3), lang)
    now = time.time()
    cached = _alerts_cache.get(cache_key)
    if cached and (now - cached['ts']) < _ALERTS_TTL:
        return jsonify(cached['data'])

    try:
        full = _google_weather_fetch(GOOGLE_ALERTS_URL, {
            'location.latitude': lat,
            'location.longitude': lng,
            'languageCode': lang,
        })

        alerts_in = full.get('weatherAlerts', []) or []
        alerts = []
        for a in alerts_in:
            title = a.get('alertTitle')
            if isinstance(title, dict):
                title = title.get('text', '')
            instr = a.get('instruction')
            if isinstance(instr, list):
                instr = ' '.join(instr)
            ds = a.get('dataSource', {}) or {}
            alerts.append({
                'id': a.get('alertId', ''),
                'title': title or '',
                'eventType': a.get('eventType', ''),
                'areaName': a.get('areaName', ''),
                'severity': a.get('severity', 'UNKNOWN'),
                'urgency': a.get('urgency', 'UNKNOWN'),
                'certainty': a.get('certainty', 'UNKNOWN'),
                'description': a.get('description', ''),
                'instruction': instr or '',
                'startTime': a.get('startTime', ''),
                'expirationTime': a.get('expirationTime', ''),
                'source': ds.get('name', ''),
                'sourceUrl': ds.get('authorityUri', ''),
            })
        result = {
            'alerts': alerts,
            'regionCode': full.get('regionCode', ''),
        }
        _alerts_cache[cache_key] = {'ts': now, 'data': result}
        return jsonify(result)
    except Exception as e:
        print(f"[google_alerts] fetch failed: {e}")
        if cached:
            return jsonify(cached['data'])
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# API: City search (for location picker) — live via Open-Meteo Geocoding, no key needed
# ---------------------------------------------------------------------------

@app.route('/api/cities')
def api_cities():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    try:
        params = urllib.parse.urlencode({
            'name': q, 'count': 10, 'language': 'en', 'format': 'json'
        })
        url = f'https://geocoding-api.open-meteo.com/v1/search?{params}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        results = []
        for c in data.get('results') or []:
            name = c.get('name', '')
            country = c.get('country', '')
            admin1 = c.get('admin1', '')
            lat = c.get('latitude')
            lng = c.get('longitude')
            tz = c.get('timezone', '')
            if not name or lat is None or lng is None:
                continue
            # Build subtitle: "Region, Country" or just "Country"
            subtitle = ', '.join(filter(None, [admin1, country]))
            results.append({
                'name': name,
                'subtitle': subtitle,
                'lat': round(lat, 4),
                'lng': round(lng, 4),
                'timezone': tz,
            })
        return jsonify(results)
    except Exception as e:
        print(f"[cities] search failed: {e}")
        return jsonify([]), 502


# ---------------------------------------------------------------------------
# API: Timezone lookup (lat/lng → IANA timezone) — cached per location
# ---------------------------------------------------------------------------

_tz_cache = {}  # {(lat,lng): 'Europe/Dublin'}


@app.route('/api/timezone')
def api_timezone():
    try:
        lat = round(float(request.args.get('lat', '0')), 1)
        lng = round(float(request.args.get('lng', '0')), 1)
    except ValueError:
        return jsonify({"error": "invalid lat/lng"}), 400

    cache_key = (lat, lng)
    if cache_key in _tz_cache:
        return jsonify({"timezone": _tz_cache[cache_key]})

    try:
        url = f'https://timeapi.io/api/timezone/coordinate?latitude={lat}&longitude={lng}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        tz = data.get('timeZone', '')
        if tz:
            _tz_cache[cache_key] = tz
        return jsonify({"timezone": tz})
    except Exception as e:
        print(f"[timezone] lookup failed: {e}")
        return jsonify({"timezone": ""}), 502


@app.route('/api/google_cal_url')
def api_google_cal_url():
    raw = os.getenv('GOOGLE_CAL_IFRAME_URL', '')
    # Extract just the src URL from the iframe HTML if needed
    return jsonify({"url": raw})


# ---------------------------------------------------------------------------
# API: Kagi News stories (science, tech, ai)
# ---------------------------------------------------------------------------

KAGI_API_BASE = 'https://kite.kagi.com/api'
_KAGI_HEADERS = {
    'Accept': 'application/json',
    'User-Agent': 'KagiNews/1.1.0 (Android)',
    '-acx-global-context': '{"platform":"android","app_version":"1.1.0","build":"84","client":"com.kagi.news"}',
}
_KAGI_CATEGORIES = ['science', 'tech', 'ai']
_KAGI_GRADIENTS = {
    'science': 'linear-gradient(160deg,#0f2027,#203a43,#2c5364)',
    'tech':    'linear-gradient(160deg,#0f0c29,#302b63,#24243e)',
    'ai':      'linear-gradient(160deg,#0d0221,#1b1b2f,#3a1a6e)',
}
_kagi_cache = {'ts': 0, 'stories': []}
_KAGI_TTL = 1800  # 30 min — Kagi batches are daily

def _kagi_get(path, params=None):
    url = f'{KAGI_API_BASE}{path}'
    if params:
        url += '?' + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    req = urllib.request.Request(url, headers=_KAGI_HEADERS)
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read())


def fetch_kagi_stories(categories=None):
    if categories is None:
        categories = _KAGI_CATEGORIES
    now = time.time()
    cache_key = ','.join(sorted(categories))
    if (_kagi_cache.get('key') == cache_key and
            _kagi_cache['stories'] and (now - _kagi_cache['ts']) < _KAGI_TTL):
        return _kagi_cache['stories']

    try:
        # 1. Resolve batch_id + category UUIDs from latest batch
        resp = _kagi_get('/batches/latest/categories', {'lang': 'default'})
        batch_id = resp.get('batchId', '')
        cat_list = resp.get('categories', [])
        cat_map = {c['categoryId']: c['id'] for c in cat_list}

        stories = []
        for cat_id in categories:
            uuid = cat_map.get(cat_id)
            if not uuid:
                print(f'[kagi] category {cat_id!r} not found in batch')
                continue
            try:
                data = _kagi_get(f'/batches/{batch_id}/categories/{uuid}/stories', {'limit': 5, 'lang': 'default'})
                for s in data.get('stories', []):
                    img = (s.get('primary_image') or {}).get('url') or (s.get('secondary_image') or {}).get('url') or ''
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
            except Exception as e:
                print(f'[kagi] stories for {cat_id} failed: {e}')

        if stories:
            _kagi_cache['stories'] = stories
            _kagi_cache['ts'] = now
            _kagi_cache['key'] = cache_key
        return stories
    except Exception as e:
        print(f'[kagi] fetch failed: {e}')
        return _kagi_cache['stories']


@app.route('/api/kagi_stories')
def api_kagi_stories():
    raw = request.args.get('categories', '')
    cats = [c.strip() for c in raw.split(',') if c.strip()] if raw else None
    return jsonify(fetch_kagi_stories(cats))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
