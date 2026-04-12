# Widgets

A minimal, customizable widget dashboard inspired by Apple, Dieter Rams design philosophy. Built with Flask and GridStack.

![Dashboard](screenshots/wallpapers.png)


## Quick Start

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5001`

## Adding a Widget

Create a folder inside `widgets/` with a `data.js` file. That's it. No middleware changes, no config — the system discovers it at runtime.

```
widgets/
  widget-my-thing/
    data.js
```

### data.js format

```javascript
module.exports = {
    "id": "widget-my-thing",
    "x": 0,
    "y": 0,
    "w": 2,
    "h": 2,
    "content": "<div class='my-widget'>Hello</div>",
    "css": "background-color: rgba(28,28,30,0.85); color: #fff; border-radius: min(28px, 15cqmin);"
};
```

| Field | Description |
|-------|-------------|
| `id` | Unique identifier, must match the folder name |
| `x`, `y` | Grid position (12-column grid) |
| `w`, `h` | Grid size in columns/rows |
| `content` | HTML content rendered inside the widget |
| `css` | Inline CSS applied to the widget container |
| `lock_ratio` | Optional. Set `true` to lock 1:1 aspect ratio on resize |
| `timezone` | Optional. IANA timezone for live clock widgets (e.g. `Europe/Dublin`) |
| `lat`, `lng` | Optional. Coordinates for sunrise/sunset widgets |

### Responsive sizing

Widget content uses CSS container queries. Use `cqmin` units for text and spacing so everything scales proportionally when the widget is resized:

```css
.my-widget {
    font-size: 12cqmin;  /* scales with widget size */
    padding: 5cqmin;
}
```

Define your widget's inner styles in `static/styles.css` using class names from your `content` HTML.

## Settings

![Settings](screenshots/settings.png)

![Wallpaper Gallery](screenshots/dashboard.png)

Access via the **Settings** link in the header:

- **Gradient presets** - 18 dark gradient backgrounds with color swatches
- **Wallpaper picker** - Browse, search, and apply with size/position/blur/dim controls
- **Widget style editor** - Per-widget theme presets, colors, opacity, blur, radius, border, shadow, font
- **Raw CSS editor** - Full control for power users

## Wallpapers

Drop images (`.png`, `.jpg`, `.webp`) into `static/wallpapers/`. They appear automatically in Settings with search and auto-generated thumbnail previews.

## Built-in Widgets

| Widget | Description |
|--------|-------------|
| `widget-apple-clock` | Live clock with timezone support, radial tick ring, SF Compact font |
| `widget-apple-calendar` | Date display with month and day |
| `widget-apple-sunrise` | Live sunrise/sunset times with animated sun arc |

## Architecture

```
app.py                  Flask server, API routes, widget/config I/O
static/
  styles.css            Design system + widget component styles
  main.js               GridStack init, layout persistence, live widgets
  wallpapers/           Drop wallpaper images here
templates/
  dashboard.html        Main dashboard with GridStack grid
  settings.html         Settings UI
widgets/
  widget-*/data.js      Widget definitions (one folder per widget)
  config.json           User settings (auto-generated, gitignored)
screenshots/            Project screenshots
```

## License

MIT
