import os
import json
import threading
import urllib.request
import subprocess
from io import BytesIO
from flask import Blueprint, request, jsonify, send_file, abort
from PIL import Image
from server.config import (WALLPAPERS_DIR, AERIALS_DIR, FONTS_DIR,
                           THUMBS_DIR, ALLOWED_IMAGE_EXT, THUMB_SIZE)

bp = Blueprint('media', __name__)

os.makedirs(AERIALS_DIR, exist_ok=True)

_AERIAL_CATALOG = []
_aerial_downloads = {}

try:
    with open('aerial_catalog.json') as _f:
        _AERIAL_CATALOG = json.load(_f)
    print(f'[aerials] loaded {len(_AERIAL_CATALOG)} videos')
except Exception as _e:
    print(f'[aerials] catalog load failed: {_e}')


@bp.route('/fonts/<path:filename>')
def serve_font(filename):
    safe = os.path.basename(filename)
    if safe != filename or '..' in filename:
        abort(400)
    path = os.path.join(FONTS_DIR, safe)
    if not os.path.isfile(path):
        abort(404)
    return send_file(path)


@bp.route('/api/wallpapers')
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
                'thumb': f'/api/thumb/{f}',
            })
    return jsonify(files)


@bp.route('/api/thumb/<path:filename>')
def api_thumb(filename):
    safe = os.path.basename(filename)
    if safe != filename or '..' in filename:
        abort(400)
    src = os.path.join(WALLPAPERS_DIR, safe)
    if not os.path.isfile(src):
        abort(404)
    os.makedirs(THUMBS_DIR, exist_ok=True)
    thumb_name = os.path.splitext(safe)[0] + '.jpg'
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
        print(f"[thumb] error for {safe}: {e}")
        abort(500)


@bp.route('/api/aerials')
def api_aerials():
    result = []
    for item in _AERIAL_CATALOG:
        vid_id = item['id']
        local_path = os.path.join(AERIALS_DIR, vid_id + '.mp4')
        if os.path.exists(local_path):
            status, progress = 'ready', 100
        elif vid_id in _aerial_downloads:
            status = _aerial_downloads[vid_id]['status']
            progress = _aerial_downloads[vid_id]['progress']
        else:
            status, progress = 'idle', 0
        result.append({'id': vid_id, 'name': item['name'],
                       'status': status, 'progress': progress})
    return jsonify(result)


@bp.route('/api/aerials/download', methods=['POST'])
def api_aerials_download():
    data = request.get_json(silent=True) or {}
    vid_id = (data.get('id') or request.form.get('id', '')).strip()
    item = next((a for a in _AERIAL_CATALOG if a['id'] == vid_id), None)
    if not item:
        return jsonify({'error': 'not found'}), 404
    local_path = os.path.join(AERIALS_DIR, vid_id + '.mp4')
    if os.path.exists(local_path):
        _aerial_downloads[vid_id] = {'status': 'ready', 'progress': 100}
        return jsonify({'status': 'ready'})
    if _aerial_downloads.get(vid_id, {}).get('status') == 'downloading':
        return jsonify({'status': 'downloading'})
    url = item.get('url_1080_h264') or item.get('url_1080_sdr', '')
    _aerial_downloads[vid_id] = {'status': 'downloading', 'progress': 0}

    def _ffmpeg_path():
        import shutil
        for p in ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg']:
            if os.path.isfile(p):
                return p
        return shutil.which('ffmpeg')

    def do_download():
        tmp = local_path + '.tmp.mov'
        try:
            def hook(count, block, total):
                if total > 0:
                    _aerial_downloads[vid_id]['progress'] = min(85, int(count * block * 85 / total))
            urllib.request.urlretrieve(url, tmp, hook)
            ffmpeg = _ffmpeg_path()
            if ffmpeg:
                _aerial_downloads[vid_id]['progress'] = 90
                res = subprocess.run(
                    [ffmpeg, '-y', '-i', tmp, '-c', 'copy', '-movflags', '+faststart', local_path],
                    capture_output=True, timeout=120,
                )
                os.remove(tmp)
                if res.returncode != 0:
                    raise RuntimeError(f'ffmpeg failed: {res.stderr.decode()[-200:]}')
            else:
                os.rename(tmp, local_path)
            _aerial_downloads[vid_id] = {'status': 'ready', 'progress': 100}
        except Exception as e:
            _aerial_downloads[vid_id] = {'status': 'error', 'progress': 0}
            for p in [local_path, tmp]:
                if os.path.exists(p):
                    os.remove(p)
            print(f'[aerials] download failed {vid_id}: {e}')

    threading.Thread(target=do_download, daemon=True).start()
    return jsonify({'status': 'downloading'})


@bp.route('/api/aerials/status')
def api_aerials_status():
    vid_id = request.args.get('id', '').strip()
    if not any(a['id'] == vid_id for a in _AERIAL_CATALOG):
        return jsonify({'error': 'not found'}), 404
    local_path = os.path.join(AERIALS_DIR, vid_id + '.mp4')
    if os.path.exists(local_path):
        status, progress = 'ready', 100
    elif vid_id in _aerial_downloads:
        status = _aerial_downloads[vid_id]['status']
        progress = _aerial_downloads[vid_id]['progress']
    else:
        status, progress = 'idle', 0
    return jsonify({
        'id': vid_id, 'status': status, 'progress': progress,
        'local_url': f'/static/aerials/{vid_id}.mp4' if status == 'ready' else None,
    })


@bp.route('/api/aerials/delete', methods=['POST'])
def api_aerials_delete():
    data = request.get_json(silent=True) or {}
    vid_id = (data.get('id') or request.form.get('id', '')).strip()
    if not any(a['id'] == vid_id for a in _AERIAL_CATALOG):
        return jsonify({'error': 'not found'}), 404
    local_path = os.path.join(AERIALS_DIR, vid_id + '.mp4')
    if os.path.exists(local_path):
        os.remove(local_path)
    _aerial_downloads.pop(vid_id, None)
    return jsonify({'status': 'ok'})


@bp.route('/api/aerials/remux_all', methods=['POST'])
def api_aerials_remux_all():
    import shutil
    ffmpeg = next(
        (p for p in ['/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg']
         if os.path.isfile(p)),
        shutil.which('ffmpeg'),
    )
    if not ffmpeg:
        return jsonify({'status': 'error', 'message': 'ffmpeg not found'}), 400
    fixed, failed = [], []
    for fname in os.listdir(AERIALS_DIR):
        if not fname.endswith('.mp4'):
            continue
        fpath = os.path.join(AERIALS_DIR, fname)
        tmp = fpath + '.remux.mp4'
        try:
            res = subprocess.run(
                [ffmpeg, '-y', '-i', fpath, '-c', 'copy', '-movflags', '+faststart', tmp],
                capture_output=True, timeout=180,
            )
            if res.returncode == 0:
                os.replace(tmp, fpath)
                fixed.append(fname)
            else:
                if os.path.exists(tmp):
                    os.remove(tmp)
                failed.append(fname)
        except Exception as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            failed.append(fname)
    return jsonify({'status': 'ok', 'fixed': fixed, 'failed': failed})


@bp.route('/api/aerials/refresh', methods=['POST'])
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
                'url_1080_sdr': asset.get('url-1080-SDR', ''),
            })
        with open('aerial_catalog.json', 'w') as f:
            json.dump(catalog, f, indent=2)
        _AERIAL_CATALOG = catalog
        return jsonify({'status': 'ok', 'count': len(catalog)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
