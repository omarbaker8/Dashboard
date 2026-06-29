import os
import json
import urllib.request
import urllib.parse
from flask import Blueprint, request, jsonify
from server.services.cache import cached

bp = Blueprint('widget_google_weather_alerts', __name__, url_prefix='/api')

_ALERTS_URL = 'https://weather.googleapis.com/v1/publicAlerts:lookup'


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


@cached(ttl=300)
def _fetch(lat, lng, lang):
    full = _gw_fetch(_ALERTS_URL, {
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
    return {'alerts': alerts, 'regionCode': full.get('regionCode', '')}


@bp.route('/google_weather_alerts')
def api_google_weather_alerts():
    if not (os.getenv('GOOGLE_WEATHER_KEY') or os.getenv('GOOGLE_WEATHER_KEY_2')):
        return jsonify({"error": "missing API key"}), 503
    try:
        lat = round(float(request.args.get('lat', '53.3498')), 3)
        lng = round(float(request.args.get('lng', '-6.2603')), 3)
    except ValueError:
        return jsonify({"error": "invalid lat/lng"}), 400
    lang = request.args.get('lang', 'en')
    try:
        return jsonify(_fetch(lat, lng, lang))
    except Exception as e:
        print(f"[google_alerts] fetch failed: {e}")
        return jsonify({"error": str(e)}), 502
