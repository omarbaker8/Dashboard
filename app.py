import os
import json
import re
import time
import urllib.request
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, abort, make_response
from PIL import Image
from io import BytesIO
from db import (get_device, create_device, list_devices, get_device_config,
                save_device_config, get_device_widgets, save_device_widget,
                init_device_widgets)

app = Flask(__name__)

WIDGETS_DIR = 'widgets'
WALLPAPERS_DIR = os.path.join('static', 'wallpapers')
THUMBS_DIR = os.path.join(WALLPAPERS_DIR, '.thumbs')
THUMB_SIZE = (280, 175)
ALLOWED_IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg')

os.makedirs(WIDGETS_DIR, exist_ok=True)


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

        device_id, name = create_device(device_type)
        # Initialize per-device widgets from base templates
        init_device_widgets(device_id, device_type, get_base_widgets())
        # Set default config
        save_device_config(device_id, {
            "background": "url('/static/wallpapers/Acrylic 4.png') no-repeat center / cover fixed",
            "bg_blur": 0,
            "bg_dim": 0,
        })

        resp = make_response(redirect(url_for('dashboard')))
        resp.set_cookie('device_id', device_id, max_age=60*60*24*365*5, httponly=True, samesite='Lax')
        return resp

    # Check if there are existing devices to offer switching
    devices = list_devices()
    return render_template('setup.html', devices=devices)


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

        if action == 'update_widget':
            widget_id = request.form.get('id', '').strip()
            new_css = request.form.get('css', '').strip()
            if widget_id and new_css:
                widgets = get_widgets_for_device(device['id'])
                for w in widgets:
                    if w['id'] == widget_id:
                        w['css'] = new_css
                        # Update location fields if provided
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
                        save_device_widget(device['id'], w)
                        break

        elif action == 'update_background':
            bg_css = request.form.get('background_css', '').strip()
            if bg_css:
                config['background'] = bg_css
            bg_blur = request.form.get('bg_blur', '0')
            bg_dim = request.form.get('bg_dim', '0')
            config['bg_blur'] = int(bg_blur) if bg_blur.isdigit() else 0
            config['bg_dim'] = int(bg_dim) if bg_dim.isdigit() else 0
            save_device_config(device['id'], config)

        return redirect(url_for('settings'))

    widgets = get_widgets_for_device(device['id'])
    return render_template('settings.html', widgets=widgets, config=config, device=device)


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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True)
