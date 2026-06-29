"""
Preset widget layouts for new device setup.
Format per entry: (widget_id, x, y, w, h, css, extra_dict)
"""
import json
from pathlib import Path

GLASS_CSS = (
    "background-color: rgba(128,128,128,0.15); "
    "backdrop-filter: blur(40px); -webkit-backdrop-filter: blur(40px); "
    "color: #ffffff; "
    "border-radius: min(28px, 15cqmin); "
    "box-shadow: 0 4px 16px rgba(0,0,0,0.15); "
    "border: 1px solid rgba(255,255,255,0.18); "
    "font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;"
)

CLOCK_ANALOGUE_CSS = (
    "background: #111111; color: #1c1c1e; "
    "border-radius: min(32px, 16cqmin); "
    "box-shadow: 0 12px 40px rgba(0,0,0,0.5);"
)

_LAPTOP_LAYOUT = [
    ("widget-apple-clock",                0,  0, 3, 3, GLASS_CSS,           {"timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-apple-calendar",             3,  0, 2, 2, GLASS_CSS,           {}),
    ("widget-apple-sunrise",              5,  0, 2, 2, GLASS_CSS,           {"lat": 53.35, "lng": -6.26}),
    ("widget-apple-calendar-2",           7,  0, 3, 3, GLASS_CSS,           {}),
    ("widget-google-wind",               10,  0, 3, 3, GLASS_CSS,           {"lat": 53.35, "lng": -6.26}),
    ("widget-apple-bbc",                 14,  0, 4, 4, GLASS_CSS,           {}),
    ("widget-apple-clock-analogue-dark",  0,  3, 3, 3, GLASS_CSS,           {"timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-apple-unsplashed",           3,  2, 4, 4, GLASS_CSS,           {}),
    ("widget-apple-pomodoro",             7,  3, 3, 3, GLASS_CSS,           {}),
    ("widget-apple-weather",             14,  4, 2, 2, GLASS_CSS,           {"lat": 53.35, "lng": -6.26, "timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-google-weather-alerts",     16,  4, 2, 2, GLASS_CSS,           {"lat": 53.35, "lng": -6.26}),
    ("widget-braun-clock",                0,  6, 3, 3, GLASS_CSS,           {"timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-google-calendar",           13,  4, 5, 5, GLASS_CSS,           {}),
    ("widget-nothing-watch",              3,  6, 3, 3, "background: #0A0A0A; border-radius: min(28px, 14cqmin); box-shadow: 0 8px 32px rgba(0,0,0,0.8);", {"timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-google-weather",            10,  4, 8, 3, GLASS_CSS,           {"lat": 53.35, "lng": -6.26, "timezone": "Europe/Dublin", "city": "Dublin", "hours_to_show": 3}),
    ("widget-mondrian",                   6,  7, 4, 4, "background-color: #F5F0E6; border-radius: min(28px, 15cqmin); overflow: hidden; box-shadow: 0 6px 28px rgba(0,0,0,0.5); border: 2px solid #111;", {"levels": 4, "stroke": 2, "split_ratio": 0.5}),
    ("widget-aljazeera-world-cup",       10,  6, 5, 5, "background: #0a0e1a; border-radius: min(28px, 15cqmin); box-shadow: 0 8px 32px rgba(0,0,0,0.85); overflow: hidden; color: #fff;", {}),
]

_TABLET_LAYOUT = [
    ("widget-apple-clock",               0,  0, 4, 4, GLASS_CSS,           {"timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-apple-calendar-2",          4,  0, 4, 4, GLASS_CSS,           {}),
    ("widget-apple-unsplashed",          8,  0, 4, 4, GLASS_CSS,           {}),
    ("widget-apple-bbc",                12,  0, 6,10, GLASS_CSS,           {}),
    ("widget-apple-clock-analogue-dark",  0,  4, 4, 4, CLOCK_ANALOGUE_CSS,  {"timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-apple-sunrise",             4,  4, 4, 4, GLASS_CSS,           {"lat": 53.35, "lng": -6.26}),
    ("widget-apple-weather",             8,  4, 4, 4, GLASS_CSS,           {"lat": 53.35, "lng": -6.26, "timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-apple-pomodoro",            0,  8, 4, 4, GLASS_CSS,           {}),
    ("widget-apple-calendar",            4,  8, 4, 4, GLASS_CSS,           {}),
    ("widget-google-wind",               8,  8, 4, 4, GLASS_CSS,           {"lat": 53.35, "lng": -6.26}),
    ("widget-google-weather-alerts",     0, 12,12, 3, GLASS_CSS,           {"lat": 53.35, "lng": -6.26}),
    ("widget-braun-clock",              12,  8, 4, 4, GLASS_CSS,           {"timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-google-calendar",           0, 15,12, 6, GLASS_CSS,           {}),
    ("widget-nothing-watch",             0, 21, 4, 4, "background: #0A0A0A; border-radius: min(28px, 14cqmin); box-shadow: 0 8px 32px rgba(0,0,0,0.8);", {"timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-google-weather",            4, 10, 8, 4, GLASS_CSS,           {"lat": 53.35, "lng": -6.26, "timezone": "Europe/Dublin", "city": "Dublin", "hours_to_show": 3}),
    ("widget-mondrian",                  0, 25, 4, 4, "background-color: #F5F0E6; border-radius: min(28px, 15cqmin); overflow: hidden; box-shadow: 0 6px 28px rgba(0,0,0,0.5); border: 2px solid #111;", {"levels": 4, "stroke": 2, "split_ratio": 0.5}),
    ("widget-aljazeera-world-cup",       0, 29, 6, 6, "background: #0a0e1a; border-radius: min(28px, 15cqmin); box-shadow: 0 8px 32px rgba(0,0,0,0.85); overflow: hidden; color: #fff;", {}),
]


def get_preset_layout(device_type):
    return _LAPTOP_LAYOUT if device_type == 'laptop' else _TABLET_LAYOUT


def get_preset_for_widget(device_type, widget_id):
    for entry in get_preset_layout(device_type):
        if entry[0] == widget_id:
            return entry
    return None


def get_location_widget_ids():
    """Derive location-aware widget IDs from manifests; fall back to static set."""
    from pathlib import Path
    from server.config import WIDGETS_DIR
    ids = set()
    widgets_path = Path(WIDGETS_DIR)
    for wdir in widgets_path.iterdir():
        if not wdir.is_dir() or wdir.name.startswith('_'):
            continue
        manifest_path = wdir / 'manifest.json'
        if manifest_path.exists():
            try:
                import json as _json
                m = _json.loads(manifest_path.read_text())
                if m.get('requires', {}).get('location'):
                    ids.add(wdir.name)
            except Exception:
                pass
    if not ids:
        # Fallback while manifests are being added
        ids = {
            'widget-apple-weather', 'widget-apple-sunrise',
            'widget-apple-clock', 'widget-apple-clock-analogue-dark',
            'widget-braun-clock', 'widget-nothing-watch',
            'widget-google-wind', 'widget-google-weather-alerts',
            'widget-google-weather', 'widget-aljazeera-world-cup',
        }
    return ids


def get_refresh_widget_defaults():
    """Derive refresh defaults from manifests; fall back to static dict."""
    from pathlib import Path
    from server.config import WIDGETS_DIR
    defaults = {}
    widgets_path = Path(WIDGETS_DIR)
    for wdir in sorted(widgets_path.iterdir()):
        if not wdir.is_dir() or wdir.name.startswith('_'):
            continue
        manifest_path = wdir / 'manifest.json'
        if manifest_path.exists():
            try:
                import json as _json
                m = _json.loads(manifest_path.read_text())
                refresh = m.get('refresh')
                if refresh:
                    defaults[wdir.name] = refresh.get('default', 900)
            except Exception:
                pass
    if not defaults:
        defaults = {
            'widget-google-calendar':       900,
            'widget-apple-bbc':             900,
            'widget-ap-news':               900,
            'widget-ap-card':               300,
            'widget-kagi-news':            1800,
            'widget-google-wind':           900,
            'widget-google-weather-alerts': 900,
            'widget-apple-weather':         900,
            'widget-google-weather':        900,
            'widget-luas-ie':               60,
            'widget-aljazeera-world-cup':   60,
        }
    return defaults
