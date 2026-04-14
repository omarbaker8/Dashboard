# Widget Specification

This folder contains all dashboard widgets. Each widget is a self-contained folder with a `data.js` file. The system auto-discovers widgets at startup — no registration needed.

## Required File

Every widget folder **must** contain a `data.js` file in this format:

```javascript
module.exports = {
    "id": "widget-name",
    "x": 0,
    "y": 0,
    "w": 2,
    "h": 2,
    "content": "<style>...</style><div>...</div><script>...</script>",
    "css": "background-color: rgba(128,128,128,0.15); ..."
};
```

## Required Fields

- **id** (string) — Unique identifier, must match the folder name
- **x** (number) — Column position on the grid (0-based, 18-column grid)
- **y** (number) — Row position on the grid (0-based)
- **w** (number) — Width in grid columns
- **h** (number) — Height in grid rows
- **content** (string) — All HTML, CSS, and JavaScript for the widget, inlined as a single string. Can include `<style>`, `<div>`, and `<script>` tags
- **css** (string) — Inline CSS applied to the widget container (`.widget-item`). Controls background, blur, text color, border-radius, shadow, border, and font. Editable via the Settings UI

## Optional Fields

- **lock_ratio** (boolean) — If `true`, enforces 1:1 aspect ratio on resize
- **lat** (number) — Latitude for location-aware widgets (weather, sunrise)
- **lng** (number) — Longitude for location-aware widgets (weather, sunrise)
- **timezone** (string) — IANA timezone string for time-aware widgets (clock, weather). Example: `"Europe/Dublin"`
- **city** (string) — Display label for the city name (clock, weather). Example: `"DUB"`

## Default Theme

All widgets ship with the **glass** theme by default:

```
background-color: rgba(128,128,128,0.15);
backdrop-filter: blur(40px);
-webkit-backdrop-filter: blur(40px);
color: #ffffff;
border-radius: min(28px, 15cqmin);
box-shadow: 0 4px 16px rgba(0,0,0,0.15);
border: 1px solid rgba(255,255,255,0.18);
font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
```

Users can change the theme per-widget in Settings.

## Content Guidelines

- Use `container-type: size` and `cqmin` units for responsive sizing within widgets
- Use `color: inherit` for primary text so the Settings text color picker works
- Keep accent colors (red badges, green labels) hardcoded — only inherit primary body text
- Use `currentColor` for SVG strokes/fills that should follow text color
- Use `border-radius: inherit` on the root element to match the container's border radius
- Wrap API calls in error handling and show a fallback message on failure
- Use `setInterval` for periodic updates (weather: 30min, clocks: 1sec, news: 5min)
- Guard against re-initialization with `if(window._myWidgetInit) return;`

## How Widgets Are Loaded

1. Flask scans this folder for subdirectories
2. For each subdirectory, reads `data.js`
3. Strips `module.exports = ` prefix and trailing `;`
4. Parses as JSON
5. Renders into the GridStack dashboard with the `css` property as inline styles and `content` as inner HTML
6. Location fields (`lat`, `lng`, `timezone`, `city`) are injected as `data-*` attributes on the `.widget-item` container

## Existing Widgets

| Widget | Type | Location Fields | Lock Ratio |
|--------|------|----------------|------------|
| widget-apple-weather | Weather forecast | lat, lng, timezone, city | yes |
| widget-apple-sunrise | Sunrise/sunset tracker | lat, lng | yes |
| widget-apple-clock | Digital clock | timezone, city | yes |
| widget-apple-clock-analogue-dark | Analogue clock | timezone, city | yes |
| widget-apple-calendar | Simple date display | — | no |
| widget-apple-calendar-2 | Monthly calendar grid | — | yes |
| widget-apple-pomodoro | Pomodoro timer | — | yes |
| widget-apple-bbc | BBC live news feed | — | no |
| widget-apple-unsplashed | Unsplash photo slideshow | — | yes |
