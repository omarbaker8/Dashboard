import json
import urllib.request
import urllib.parse
from flask import Blueprint, request, jsonify

bp = Blueprint('location', __name__)

_tz_cache = {}


@bp.route('/api/cities')
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
            lat = c.get('latitude')
            lng = c.get('longitude')
            if not name or lat is None or lng is None:
                continue
            subtitle = ', '.join(filter(None, [c.get('admin1', ''), c.get('country', '')]))
            results.append({
                'name': name,
                'subtitle': subtitle,
                'lat': round(lat, 4),
                'lng': round(lng, 4),
                'timezone': c.get('timezone', ''),
            })
        return jsonify(results)
    except Exception as e:
        print(f"[cities] search failed: {e}")
        return jsonify([]), 502


@bp.route('/api/timezone')
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
