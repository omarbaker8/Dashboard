# Widget Developer Specification

Complete technical reference for building widgets in this dashboard. Every widget is a self-contained folder — the system auto-discovers them at startup with no registration required.

---

## Table of Contents

1. [File Structure](#file-structure)
2. [data.js Schema](#datajs-schema)
3. [Required Fields](#required-fields)
4. [Optional Fields](#optional-fields)
5. [The `extra` System](#the-extra-system)
6. [Grid System](#grid-system)
7. [CSS — Glass Theme](#css--glass-theme)
8. [CSS — Custom Themes](#css--custom-themes)
9. [Content Guidelines](#content-guidelines)
10. [Responsive Sizing — cqmin Units](#responsive-sizing--cqmin-units)
11. [Fonts](#fonts)
12. [Location-Aware Widgets](#location-aware-widgets)
13. [Refresh Interval Setting](#refresh-interval-setting)
14. [Backend API Routes](#backend-api-routes)
15. [Environment Variables](#environment-variables)
16. [Adding to Preset Layouts](#adding-to-preset-layouts)
17. [Registering as Location-Aware](#registering-as-location-aware)
18. [Settings UI Integration](#settings-ui-integration)
19. [Init Guard Pattern](#init-guard-pattern)
20. [Widget Checklist](#widget-checklist)
21. [Existing Widgets](#existing-widgets)

---

## File Structure

```
widgets/
  widget-my-new-widget/
    data.js          ← required
    style.md         ← optional, design reference notes
```

The folder name **must match** the `id` field inside `data.js`. The system loads every folder that contains a `data.js`.

---

## data.js Schema

```javascript
module.exports = {
    "id":         "widget-my-new-widget",   // string, matches folder name
    "x":          0,                        // number, grid column (0–17)
    "y":          0,                        // number, grid row (0-based)
    "w":          3,                        // number, width in columns
    "h":          3,                        // number, height in rows
    "lock_ratio": true,                     // optional boolean
    "lat":        53.3498,                  // optional, location widgets
    "lng":        -6.2603,                  // optional, location widgets
    "timezone":   "Europe/Dublin",          // optional, clock/weather widgets
    "city":       "Dublin",                 // optional, display label
    "content":    "<style>…</style><div>…</div><script>…</script>",
    "css":        "background-color: rgba(128,128,128,0.15); …"
};
```

The file is loaded by Flask via Node.js-style parsing: `module.exports =` is stripped, the remainder is parsed as JSON. **All string values must be valid JSON** — no unescaped single quotes, no trailing commas.

---

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier. Must match the folder name exactly. Convention: `widget-<brand>-<name>` |
| `x` | number | Starting column on the 18-column grid (0-based) |
| `y` | number | Starting row (0-based) |
| `w` | number | Width in grid columns |
| `h` | number | Height in grid rows |
| `content` | string | All widget HTML, CSS, and JS as a single escaped string |
| `css` | string | Inline CSS applied to the outer `.widget-item` container |

---

## Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lock_ratio` | boolean | `false` | Forces 1:1 aspect ratio on resize. Use for clocks and square widgets |
| `lat` | number | — | Latitude for location-aware widgets |
| `lng` | number | — | Longitude for location-aware widgets |
| `timezone` | string | — | IANA timezone string e.g. `"Europe/Dublin"`, `"America/New_York"` |
| `city` | string | — | City display label. Clocks show the first 3 letters uppercase |
| `refresh_interval` | number | widget default | Polling interval in **seconds**, stored per-device in the DB |

---

## The `extra` System

Every field in `data.js` beyond `id`, `x`, `y`, `w`, `h`, `css`, `content`, and `lock_ratio` is treated as **extra data** and stored in the `device_widgets.extra` JSON column in SQLite. This includes `lat`, `lng`, `timezone`, `city`, `refresh_interval`, and any custom fields you add.

When the dashboard renders a widget, extra fields are merged into the widget dict and injected as `data-*` attributes on the `.widget-item` container:

```html
<div class="widget-item"
     style="…css…"
     data-lat="53.3498"
     data-lng="-6.2603"
     data-timezone="Europe/Dublin"
     data-city="Dublin"
     data-refresh="900">
    <!-- content injected here -->
</div>
```

Your widget JS reads these at runtime:

```javascript
var wi = document.getElementById('my-root').closest('.widget-item');
var lat = parseFloat(wi && wi.dataset.lat) || 53.3498;
var tz  = (wi && wi.dataset.timezone) || 'Europe/Dublin';
```

This means widget JS never hardcodes per-device values — the DB drives them.

---

## Grid System

- **18 columns**, no fixed row height (rows size to content)
- Powered by **GridStack.js v10**
- Grid columns are referenced 0–17
- `x + w` must not exceed 18
- Typical sizes:

| Use case | w × h |
|----------|-------|
| Small square (clock, calendar) | 2×2 or 3×3 |
| Medium tile (weather, wind) | 3×3 or 4×4 |
| Wide card (news, alerts) | 4×4 to 6×6 |
| Full-width banner | 12×3 to 18×3 |

---

## CSS — Glass Theme

Every widget **must** ship with the glass theme as its default `css` value. This ensures a consistent look and makes the Settings color picker work correctly.

```
background-color: rgba(128,128,128,0.15); backdrop-filter: blur(40px); -webkit-backdrop-filter: blur(40px); color: #ffffff; border-radius: min(28px, 15cqmin); box-shadow: 0 4px 16px rgba(0,0,0,0.15); border: 1px solid rgba(255,255,255,0.18); font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
```

This is exported from `db.py` as `GLASS_CSS` and used in all preset layouts.

**What each part does:**

| Property | Purpose |
|----------|---------|
| `background-color: rgba(128,128,128,0.15)` | Translucent neutral base |
| `backdrop-filter: blur(40px)` | Frosted glass blur over wallpaper |
| `color: #ffffff` | Default text color, overridden per-widget in Settings |
| `border-radius: min(28px, 15cqmin)` | Rounded corners that scale with widget size |
| `box-shadow` | Depth separation from wallpaper |
| `border: 1px solid rgba(255,255,255,0.18)` | Subtle light edge |
| `font-family` | SF Pro Display system font stack |

---

## CSS — Custom Themes

Some widgets use a fixed custom CSS instead of glass when the design demands it (e.g. the analogue dark clock which has its own background color):

```
background: #1C1C1D; border-radius: min(32px, 16cqmin); box-shadow: 0 8px 32px rgba(0,0,0,0.6);
```

Use a custom CSS string when:
- The widget has its own opaque background (clocks, photo widgets)
- The design spec defines a specific background color
- Transparency would look wrong

---

## Content Guidelines

The `content` field is a single JSON string containing everything the widget renders. Structure it as:

```
"<style>…</style><div id='my-root'>…</div><script>…</script>"
```

### Root element

- Give the root element a unique `id` (e.g. `id='weather-root'`)
- Set `border-radius: inherit` so it matches the container's rounded corners
- Set `overflow: hidden` to clip content to the rounded shape
- Set `width: 100%; height: 100%` to fill the grid cell
- Set `container-type: size; container-name: mywidgetc` on the root for `cqmin` units

### Colors

- Use `color: inherit` for primary text — this lets the Settings color picker control it
- Hardcode accent colors that must not change (e.g. BBC red `#E5072F`, alert orange `#FF9F0A`)
- Use `currentColor` for SVG strokes/fills that should follow the text color setting

### Error handling

Every API call must have a `.catch()` that shows a user-visible fallback:

```javascript
fetch('/api/my_endpoint')
    .then(function(r) { return r.json(); })
    .then(render)
    .catch(function() {
        root.innerHTML = "<div class='loading'>⚠️ Unavailable</div>";
    });
```

---

## Responsive Sizing — cqmin Units

All sizing inside a widget **must use `cqmin`** (container query min-axis units), not `px`, `em`, or `vw`. This makes the widget look correct at any grid size.

**Setup required on the root element:**

```css
.my-widget {
    container-type: size;
    container-name: mywidgetc;
    width: 100%;
    height: 100%;
}
```

**Usage:**

```css
.my-title   { font-size: 8cqmin; }
.my-icon    { width: 12cqmin; height: 12cqmin; }
.my-padding { padding: 5cqmin 6cqmin; }
```

**Rules:**
- Never use `px` for font sizes or layout inside the widget
- Use `max(1px, 0.Xcqmin)` for thin lines/borders that might go sub-pixel on small widgets
- Use `min(28px, 15cqmin)` pattern for values that should cap at a pixel maximum

---

## Fonts

### System font (free, always available)

```css
font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
```

Use this for all standard text. It automatically uses SF Pro on macOS/iOS.

### SF Pro via local file (for precise weight control)

A local copy of `SFNS.ttf` is served by the Flask app at `/fonts/SFNS.ttf`. Use this when you need fine-grained weight control (100–900):

```css
@font-face {
    font-family: 'WW';
    src: url('/fonts/SFNS.ttf') format('truetype');
    font-weight: 100 900;
}
.my-element { font-family: 'WW', -apple-system, system-ui, sans-serif; }
```

The file is at `static/fonts/SFNS.ttf`. Flask serves it via the `/fonts/<filename>` route.

### Font weight reference (SF Pro / Apple HIG)

| Weight | Value | Typical use |
|--------|-------|-------------|
| Ultralight | 100 | Large display numbers |
| Thin | 200 | Temperature, big stats |
| Light | 300 | Hero numbers (e.g. weather temp) |
| Regular | 400 | Body text |
| Medium | 500 | Labels, city names |
| Semibold | 600 | Section headers, widget titles |
| Bold | 700 | Strong labels, BBC header |
| Heavy | 800 | Brand names |
| Black | 900 | — |

---

## Location-Aware Widgets

Widgets that need a user's location (weather, wind, sunrise, clocks) receive coordinates via `data-*` attributes on the `.widget-item` container.

### Reading location in widget JS

```javascript
var wi  = document.getElementById('my-root').closest('.widget-item');
var lat = parseFloat(wi && wi.dataset.lat)      || 53.3498;   // Dublin fallback
var lng = parseFloat(wi && wi.dataset.lng)      || -6.2603;
var tz  = (wi && wi.dataset.timezone)           || 'Europe/Dublin';
var city = (wi && wi.dataset.city)              || 'Dublin';
```

Always provide a sensible fallback (Dublin defaults throughout this project).

### Declaring location fields in data.js

```javascript
"lat":      53.3498,
"lng":      -6.2603,
"timezone": "Europe/Dublin",
"city":     "Dublin",
```

### Registering in LOCATION_WIDGETS (db.py)

If your widget uses location and you want the unified location dropdown in Settings to appear for it, add its ID to the `LOCATION_WIDGETS` set in `db.py`:

```python
LOCATION_WIDGETS = {
    'widget-apple-weather', 'widget-apple-sunrise',
    'widget-apple-clock',   'widget-apple-clock-analogue-dark',
    'widget-braun-clock',
    'widget-google-wind',   'widget-google-weather-alerts',
    'widget-my-new-widget',   # ← add yours here
}
```

This causes the location country dropdown to appear in the widget's Settings card, and the setup wizard to pre-populate your widget's lat/lng/timezone/city from the device's default location.

### City display convention

Clocks display the city name as **3 uppercase letters**:

```javascript
document.querySelector('.city-el').textContent = city.slice(0, 3).toUpperCase();
```

---

## Refresh Interval Setting

Widgets that poll an API should support a user-configurable refresh interval. The interval is stored per-device in the `extra` JSON blob and delivered via `data-refresh="<seconds>"` on the container.

### Reading the interval in widget JS

```javascript
function load() { /* fetch and render */ }
load();

var container = document.getElementById('my-root').closest('[data-refresh]');
var ms = (parseInt((container && container.dataset.refresh) || '900', 10)) * 1000;
setInterval(load, ms);
```

The fallback value (second argument to `||`) should be your widget's default in seconds. All polling widgets in this project default to **900s (15 minutes)**.

### Declaring a default in data.js

```javascript
"refresh_interval": 900
```

### Showing the setting in the Settings UI

Add your widget ID to the `_refresh_widgets` dict inside the widget editor loop in `templates/settings.html`:

```jinja
{% set _refresh_widgets = {
    'widget-google-calendar':       900,
    'widget-apple-bbc':             900,
    'widget-google-wind':           900,
    'widget-google-weather-alerts': 900,
    'widget-apple-weather':         900,
    'widget-my-new-widget':         900,   ← add yours
} %}
```

The `update_widget` handler in `app.py` already saves `refresh_interval` for any widget — no backend change needed.

---

## Backend API Routes

These routes are available to all widgets via `fetch()`:

| Route | Method | Description | Auth |
|-------|--------|-------------|------|
| `/api/bbc_news` | GET | BBC live news items (cached 15 min) | none |
| `/api/google_wind` | GET | Wind speed/direction. Params: `lat`, `lng` | `GOOGLE_WEATHER_KEY` |
| `/api/google_weather_alerts` | GET | Active weather alerts. Params: `lat`, `lng`, `lang` | `GOOGLE_WEATHER_KEY` |
| `/api/google_cal_url` | GET | Returns Google Calendar iframe URL from `.env` | none |
| `/api/countries` | GET | Country list with lat/lng for location picker (cached) | none |
| `/api/timezone` | GET | IANA timezone from coordinates. Params: `lat`, `lng` | none |
| `/api/wallpapers` | GET | Available wallpaper files | none |
| `/api/update_layout` | POST | Save GridStack layout positions | none |

For weather/wind, the server caches results server-side so rapid widget refreshes don't exhaust the API quota.

### Adding a new backend route

Add it to `app.py` before the `if __name__ == '__main__':` block:

```python
@app.route('/api/my_data')
def api_my_data():
    # fetch, cache, return
    return jsonify({"key": "value"})
```

Use server-side caching for any external API to avoid rate limits:

```python
_my_cache = {}
_MY_TTL = 900  # 15 minutes

@app.route('/api/my_data')
def api_my_data():
    now = time.time()
    if _my_cache.get('data') and (now - _my_cache['ts']) < _MY_TTL:
        return jsonify(_my_cache['data'])
    # ... fetch ...
    _my_cache.update({'data': result, 'ts': now})
    return jsonify(result)
```

---

## Environment Variables

Secrets are stored in `.env` (gitignored) and loaded via `python-dotenv`. Never hardcode secrets in widget JS or `data.js` — they would be committed to the repo.

Current variables:

| Variable | Used by |
|----------|---------|
| `GOOGLE_WEATHER_KEY` | `/api/google_wind`, `/api/google_weather_alerts` |
| `GOOGLE_CAL_IFRAME_URL` | `/api/google_cal_url` |

To add a new secret:

1. Add to `.env`: `MY_API_KEY = "..."`
2. Read in `app.py`: `key = os.getenv('MY_API_KEY')`
3. Add to `.env.example` with a placeholder value so other users know what to set

---

## Adding to Preset Layouts

New widgets should be added to the default layouts in `db.py` so they appear for new device setups:

```python
# db.py
_LAPTOP_LAYOUT = [
    ...
    ("widget-my-new-widget", 13, 6, 5, 4, GLASS_CSS, {}),
    # ^ id              x   y  w  h  css      extra
]

_TABLET_LAYOUT = [
    ...
    ("widget-my-new-widget", 0, 18, 12, 4, GLASS_CSS, {}),
]
```

For location-aware widgets, include defaults in the extra dict:

```python
("widget-my-new-widget", 0, 6, 3, 3, GLASS_CSS, {"lat": 53.3498, "lng": -6.2603}),
```

The layout is only applied on **first setup** for a new device. Existing devices need a "Reset to preset" action in Settings to pick up changes.

---

## Registering as Location-Aware

Summary of all the places to touch when building a location-aware widget:

1. **`data.js`** — include `lat`, `lng`, `timezone`, `city` fields with Dublin defaults
2. **widget JS** — read from `wi.dataset.lat` etc., with fallbacks
3. **`db.py` `LOCATION_WIDGETS`** — add the widget ID to the set
4. **`db.py` preset layouts** — include `{"lat": 53.3498, "lng": -6.2603}` in extra dict

---

## Settings UI Integration

The Settings page (`templates/settings.html`) auto-generates a card for every active widget. Each card includes theme/color/blur/font controls. You get this for free.

For **location widgets**, a country search dropdown appears automatically once the widget ID is in `LOCATION_WIDGETS`.

For **custom per-widget settings** (like refresh interval), add them in the `{% for widget in widgets %}` loop inside the widget editor section, gated by `{% if widget.id == 'widget-my-new-widget' %}`.

The hidden form that saves settings is `form-{{ loop.index0 }}`. Any custom hidden input named after a key will be saved into the `extra` JSON blob automatically — as long as the key is handled in the `update_widget` block in `app.py`.

---

## Init Guard Pattern

Widgets can be re-rendered when settings change. Always guard initialization to prevent duplicate `setInterval` timers:

```javascript
(function() {
    if (window._myWidgetInit) return;
    window._myWidgetInit = true;

    var root = document.getElementById('my-root');
    // ... setup ...

    function load() { /* fetch */ }
    load();

    var container = root.closest('[data-refresh]');
    var ms = (parseInt((container && container.dataset.refresh) || '900', 10)) * 1000;
    setInterval(load, ms);
})();
```

Use a globally unique flag name per widget (e.g. `_bbcInit`, `_gwInit`, `_wwInit`).

---

## Widget Checklist

Use this before submitting a new widget:

- [ ] Folder name matches `id` in `data.js`
- [ ] `content` is a valid JSON string (all inner quotes escaped)
- [ ] Root element has `container-type: size` and `container-name`
- [ ] All sizing uses `cqmin`, not `px`
- [ ] Root element has `border-radius: inherit` and `overflow: hidden`
- [ ] Default `css` uses `GLASS_CSS` (or a justified custom value)
- [ ] Primary text uses `color: inherit`
- [ ] Init guard `if (window._xyzInit) return` present
- [ ] All `fetch()` calls have `.catch()` with fallback UI
- [ ] `setInterval` reads `data-refresh` from the container with a fallback default
- [ ] No API keys or personal data hardcoded in `data.js`
- [ ] If location-aware: added to `LOCATION_WIDGETS` in `db.py`
- [ ] If location-aware: reads `wi.dataset.lat/lng/timezone/city` with Dublin fallbacks
- [ ] Added to `_LAPTOP_LAYOUT` and `_TABLET_LAYOUT` in `db.py`
- [ ] If using a backend API: route added to `app.py` with server-side caching

---

## Existing Widgets

| Widget ID | Description | Location fields | Refresh interval | Lock ratio |
|-----------|-------------|----------------|-----------------|------------|
| `widget-apple-clock` | Digital clock with timezone | timezone, city | — (1s tick) | yes |
| `widget-apple-clock-analogue-dark` | Dark analogue clock | timezone, city | — (1s tick) | yes |
| `widget-braun-clock` | Braun-style analogue clock | timezone, city | — (1s tick) | yes |
| `widget-apple-calendar` | Date display | — | — | no |
| `widget-apple-calendar-2` | Monthly calendar grid | — | — | yes |
| `widget-apple-weather` | Weather forecast (Open-Meteo) | lat, lng, timezone, city | 15 min | yes |
| `widget-apple-sunrise` | Sunrise/sunset tracker | lat, lng | 10 min | no |
| `widget-apple-pomodoro` | Pomodoro timer | — | — | yes |
| `widget-apple-bbc` | BBC live news feed | — | 15 min | no |
| `widget-apple-unsplashed` | Unsplash photo slideshow | — | — | yes |
| `widget-google-wind` | Wind speed & direction | lat, lng | 15 min | no |
| `widget-google-weather-alerts` | Active weather alerts | lat, lng | 15 min | no |
| `widget-google-calendar` | Google Calendar iframe | — | 15 min | no |
