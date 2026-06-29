import os
import json
import urllib.request
import urllib.parse
from flask import Blueprint, request, jsonify
from server.services.cache import cached

bp = Blueprint('widget_google_wind', __name__, url_prefix='/api')

_GOOGLE_WEATHER_URL = 'https://weather.googleapis.com/v1/currentConditions:lookup'


def _gw_fetch(url_base, params_base):
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
            last_exc = e
    raise last_exc


@cached(ttl=600)
def _fetch(lat, lng):
    full = _gw_fetch(_GOOGLE_WEATHER_URL, {
        'location.latitude': lat,
        'location.longitude': lng,
    })
    wind = full.get('wind', {})
    return {
        'speed': (wind.get('speed') or {}).get('value'),
        'gust': (wind.get('gust') or {}).get('value'),
        'direction': (wind.get('direction') or {}).get('degrees'),
        'cardinal': (wind.get('direction') or {}).get('cardinal', ''),
        'unit': (wind.get('speed') or {}).get('unit', 'KILOMETERS_PER_HOUR'),
    }


@bp.route('/google_wind')
def api_google_wind():
    if not (os.getenv('GOOGLE_WEATHER_KEY') or os.getenv('GOOGLE_WEATHER_KEY_2')):
        return jsonify({"error": "missing API key"}), 503
    try:
        lat = round(float(request.args.get('lat', '53.3498')), 3)
        lng = round(float(request.args.get('lng', '-6.2603')), 3)
    except ValueError:
        return jsonify({"error": "invalid lat/lng"}), 400
    try:
        return jsonify(_fetch(lat, lng))
    except Exception as e:
        print(f"[google_wind] fetch failed: {e}")
        return jsonify({"error": str(e)}), 502
