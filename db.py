"""
SQLite database layer for device management.
Each device has its own widget layout/settings and global config.
"""

import sqlite3
import os
import json
import random

DB_PATH = os.path.join(os.path.dirname(__file__), 'dashboard.db')

# ---------------------------------------------------------------------------
# Random name generator (DigitalOcean / Heroku style)
# ---------------------------------------------------------------------------

_ADJECTIVES = [
    'amber', 'bold', 'brave', 'bright', 'calm', 'clever', 'cosmic', 'crisp',
    'crystal', 'daring', 'dawn', 'deep', 'digital', 'dreamy', 'dusk', 'echo',
    'ember', 'ethereal', 'fading', 'fierce', 'floral', 'flowing', 'foggy',
    'frosty', 'gentle', 'gilded', 'glass', 'glowing', 'golden', 'grand',
    'hazy', 'hidden', 'hollow', 'hushed', 'icy', 'iron', 'jade', 'keen',
    'laser', 'lemon', 'light', 'liquid', 'lunar', 'maple', 'marble',
    'meadow', 'mighty', 'misty', 'mossy', 'neon', 'nimble', 'noble', 'nova',
    'opal', 'orchid', 'pastel', 'pearl', 'phantom', 'pine', 'pixel',
    'polar', 'prism', 'proud', 'quiet', 'rapid', 'raven', 'rising', 'rosy',
    'ruby', 'rustic', 'sable', 'sage', 'scarlet', 'shadow', 'shining',
    'silent', 'silver', 'sleek', 'snowy', 'solar', 'spark', 'starry',
    'steady', 'still', 'storm', 'swift', 'tidal', 'timber', 'twilight',
    'velvet', 'violet', 'vivid', 'wandering', 'warm', 'wild', 'winter',
    'woven', 'zen',
]

_NOUNS = [
    'anchor', 'atlas', 'aurora', 'beacon', 'birch', 'breeze', 'brook',
    'canyon', 'cedar', 'cliff', 'cloud', 'comet', 'coral', 'cove', 'crane',
    'creek', 'crest', 'dawn', 'delta', 'dune', 'eagle', 'echo', 'ember',
    'falcon', 'fern', 'field', 'flame', 'flare', 'flower', 'forest',
    'fountain', 'fox', 'frost', 'garden', 'glacier', 'grove', 'harbor',
    'hawk', 'heron', 'hill', 'horizon', 'island', 'lagoon', 'lake', 'lark',
    'leaf', 'lynx', 'maple', 'marsh', 'meadow', 'mist', 'moon', 'moss',
    'mountain', 'nebula', 'oak', 'ocean', 'orchid', 'osprey', 'otter',
    'owl', 'palm', 'panda', 'peak', 'pebble', 'phoenix', 'pine', 'plains',
    'pond', 'prairie', 'rain', 'rapids', 'reef', 'ridge', 'river', 'robin',
    'sage', 'shore', 'sky', 'snow', 'sparrow', 'spring', 'star', 'stone',
    'stream', 'summit', 'sun', 'swan', 'thunder', 'tide', 'trail', 'tulip',
    'valley', 'wave', 'willow', 'wind', 'wolf', 'wren',
]


def generate_device_name():
    return f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}"


# ---------------------------------------------------------------------------
# DB init
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS devices (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL CHECK(type IN ('laptop', 'tablet')),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS device_config (
            device_id   TEXT NOT NULL REFERENCES devices(id),
            key         TEXT NOT NULL,
            value       TEXT NOT NULL,
            PRIMARY KEY (device_id, key)
        );

        CREATE TABLE IF NOT EXISTS device_widgets (
            device_id   TEXT NOT NULL REFERENCES devices(id),
            widget_id   TEXT NOT NULL,
            x           INTEGER NOT NULL,
            y           INTEGER NOT NULL,
            w           INTEGER NOT NULL,
            h           INTEGER NOT NULL,
            css         TEXT NOT NULL DEFAULT '',
            extra       TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (device_id, widget_id)
        );
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Device CRUD
# ---------------------------------------------------------------------------

def create_device(device_type):
    """Create a new device, return its id and name."""
    import uuid
    device_id = uuid.uuid4().hex[:12]
    name = generate_device_name()
    # Ensure unique name
    conn = get_db()
    for _ in range(10):
        if not conn.execute("SELECT 1 FROM devices WHERE name=?", (name,)).fetchone():
            break
        name = generate_device_name()
    conn.execute("INSERT INTO devices (id, name, type) VALUES (?, ?, ?)",
                 (device_id, name, device_type))
    conn.commit()
    conn.close()
    return device_id, name


def get_device(device_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_devices():
    conn = get_db()
    rows = conn.execute("SELECT * FROM devices ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Per-device config
# ---------------------------------------------------------------------------

def get_device_config(device_id, defaults=None):
    """Return config dict for device, merged with defaults."""
    result = dict(defaults or {"background": "#0a0a0a", "bg_blur": 0, "bg_dim": 0})
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM device_config WHERE device_id=?",
                        (device_id,)).fetchall()
    conn.close()
    for r in rows:
        val = r['value']
        # Try to parse numbers
        try:
            val = int(val)
        except ValueError:
            try:
                val = float(val)
            except ValueError:
                pass
        result[r['key']] = val
    return result


def save_device_config(device_id, config):
    conn = get_db()
    for k, v in config.items():
        conn.execute(
            "INSERT OR REPLACE INTO device_config (device_id, key, value) VALUES (?, ?, ?)",
            (device_id, k, str(v)))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Per-device widgets
# ---------------------------------------------------------------------------

def get_device_widgets(device_id, base_widgets):
    """Return widgets list for device. If device has overrides, apply them on top of base widgets."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM device_widgets WHERE device_id=?",
                        (device_id,)).fetchall()
    conn.close()

    # If device has no per-device rows at all (legacy), show all base widgets.
    if not rows:
        return base_widgets

    # Device has explicit rows: only include widgets that are in device_widgets.
    # Merge each row with its base widget template for content/lock_ratio.
    base_by_id = {bw['id']: bw for bw in base_widgets}
    result = []
    for r in rows:
        wid = r['widget_id']
        bw = base_by_id.get(wid)
        if not bw:
            continue  # base widget no longer exists on disk
        w = dict(bw)
        w['x'] = r['x']
        w['y'] = r['y']
        w['w'] = r['w']
        w['h'] = r['h']
        if r['css']:
            w['css'] = r['css']
        extra = json.loads(r['extra'] or '{}')
        w.update(extra)
        result.append(w)
    return sorted(result, key=lambda x: x.get('id', ''))


def save_device_widget(device_id, widget):
    """Save a single widget's per-device overrides."""
    extra_keys = {k: v for k, v in widget.items()
                  if k not in ('id', 'x', 'y', 'w', 'h', 'css', 'content', 'lock_ratio')}
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO device_widgets
            (device_id, widget_id, x, y, w, h, css, extra)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (device_id, widget['id'], widget['x'], widget['y'],
          widget['w'], widget['h'], widget.get('css', ''),
          json.dumps(extra_keys)))
    conn.commit()
    conn.close()


GLASS_CSS = "background-color: rgba(128,128,128,0.15); backdrop-filter: blur(40px); -webkit-backdrop-filter: blur(40px); color: #ffffff; border-radius: min(28px, 15cqmin); box-shadow: 0 4px 16px rgba(0,0,0,0.15); border: 1px solid rgba(255,255,255,0.18); font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;"
CLOCK_ANALOGUE_CSS = "background: #111111; color: #1c1c1e; border-radius: min(32px, 16cqmin); box-shadow: 0 12px 40px rgba(0,0,0,0.5);"

DEFAULT_CONFIG = {
    "background": "url('/static/wallpapers/Aligned.png') no-repeat center / cover fixed",
    "bg_blur": 0,
    "bg_dim": 0,
}

# Pre-baked layouts from reference devices (proud-cloud laptop, winter-sparrow tablet)
# Format: (widget_id, x, y, w, h, css, extra_dict)
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
]

_TABLET_LAYOUT = [
    ("widget-apple-clock",               0,  0, 4, 4, GLASS_CSS,           {"timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-apple-calendar-2",          4,  0, 4, 4, GLASS_CSS,           {}),
    ("widget-apple-unsplashed",          8,  0, 4, 4, GLASS_CSS,           {}),
    ("widget-apple-bbc",                12,  0, 6,10, GLASS_CSS,           {}),
    ("widget-apple-clock-analogue-dark",  0, 4, 4, 4, CLOCK_ANALOGUE_CSS,  {"timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-apple-sunrise",             4,  4, 4, 4, GLASS_CSS,           {"lat": 53.35, "lng": -6.26}),
    ("widget-apple-weather",             8,  4, 4, 4, GLASS_CSS,           {"lat": 53.35, "lng": -6.26, "timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-apple-pomodoro",            0,  8, 4, 4, GLASS_CSS,           {}),
    ("widget-apple-calendar",            4,  8, 4, 4, GLASS_CSS,           {}),
    ("widget-google-wind",               8,  8, 4, 4, GLASS_CSS,           {"lat": 53.35, "lng": -6.26}),
    ("widget-google-weather-alerts",     0, 12, 12, 3, GLASS_CSS,          {"lat": 53.35, "lng": -6.26}),
    ("widget-braun-clock",              12,  8, 4, 4, GLASS_CSS,           {"timezone": "Europe/Dublin", "city": "Dublin"}),
    ("widget-google-calendar",           0, 15, 12, 6, GLASS_CSS,           {}),
    ("widget-nothing-watch",             0, 21,  4, 4, "background: #0A0A0A; border-radius: min(28px, 14cqmin); box-shadow: 0 8px 32px rgba(0,0,0,0.8);", {"timezone": "Europe/Dublin", "city": "Dublin"}),
]


def get_preset_layout(device_type):
    """Return the preset layout list for a device type."""
    return _LAPTOP_LAYOUT if device_type == 'laptop' else _TABLET_LAYOUT


def get_preset_for_widget(device_type, widget_id):
    """Return preset entry for a single widget, or None."""
    for entry in get_preset_layout(device_type):
        if entry[0] == widget_id:
            return entry
    return None


# Widget IDs that use lat/lng location
LOCATION_WIDGETS = {
    'widget-apple-weather', 'widget-apple-sunrise',
    'widget-apple-clock', 'widget-apple-clock-analogue-dark',
    'widget-braun-clock', 'widget-nothing-watch',
    'widget-google-wind', 'widget-google-weather-alerts',
}


def init_device_widgets(device_id, device_type, base_widgets, selected_ids=None,
                        default_lat=None, default_lng=None, default_city=None,
                        default_timezone=None):
    """Initialize widget layout for a new device using preset layouts.

    If selected_ids is provided, only those widgets are inserted.
    If default location provided, overrides location on all location-aware widgets.
    """
    layout = get_preset_layout(device_type)
    base_ids = {bw['id'] for bw in base_widgets}
    sel = set(selected_ids) if selected_ids is not None else None

    conn = get_db()
    for (wid, x, y, w, h, css, extra) in layout:
        if wid not in base_ids:
            continue
        if sel is not None and wid not in sel:
            continue
        row_extra = dict(extra)
        if wid in LOCATION_WIDGETS and default_lat is not None and default_lng is not None:
            row_extra['lat'] = default_lat
            row_extra['lng'] = default_lng
            if default_city:
                row_extra['city'] = default_city
            if default_timezone:
                row_extra['timezone'] = default_timezone
        conn.execute("""
            INSERT OR REPLACE INTO device_widgets
                (device_id, widget_id, x, y, w, h, css, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (device_id, wid, x, y, w, h, css, json.dumps(row_extra)))
    conn.commit()
    conn.close()


def add_device_widget(device_id, device_type, widget_id, base_widget=None,
                      default_lat=None, default_lng=None, default_city=None,
                      default_timezone=None):
    """Add a widget to a device using its preset layout (or sensible defaults)."""
    preset = get_preset_for_widget(device_type, widget_id)
    if preset:
        wid, x, y, w, h, css, extra = preset
        extra = dict(extra)
        if wid in LOCATION_WIDGETS and default_lat is not None and default_lng is not None:
            extra['lat'] = default_lat
            extra['lng'] = default_lng
            if default_city:
                extra['city'] = default_city
            if default_timezone:
                extra['timezone'] = default_timezone
    else:
        # Fall back to base widget defaults
        bw = base_widget or {}
        wid = widget_id
        x = bw.get('x', 0)
        y = bw.get('y', 0)
        w = bw.get('w', 3)
        h = bw.get('h', 3)
        css = bw.get('css', GLASS_CSS)
        extra = {k: v for k, v in bw.items()
                 if k not in ('id', 'x', 'y', 'w', 'h', 'css', 'content', 'lock_ratio')}

    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO device_widgets
            (device_id, widget_id, x, y, w, h, css, extra)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (device_id, wid, x, y, w, h, css, json.dumps(extra)))
    conn.commit()
    conn.close()


def remove_device_widget(device_id, widget_id):
    """Remove a widget from a device."""
    conn = get_db()
    conn.execute("DELETE FROM device_widgets WHERE device_id=? AND widget_id=?",
                 (device_id, widget_id))
    conn.commit()
    conn.close()


def get_device_widget_ids(device_id):
    """Return set of widget_ids currently assigned to a device."""
    conn = get_db()
    rows = conn.execute("SELECT widget_id FROM device_widgets WHERE device_id=?",
                        (device_id,)).fetchall()
    conn.close()
    return {r['widget_id'] for r in rows}


# Initialize on import
init_db()
