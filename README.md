# Dashboard

A minimal, multi-device widget dashboard where any widget can be built by describing it to an LLM. The framework is designed so that Claude, GPT, or any model has everything it needs — a typed manifest, auto-registration, and a clear JS contract — to produce a working widget in one shot.

![Demo](https://github.com/user-attachments/assets/f78c87cd-c1de-46bb-b103-72d13c6e4b77)

---

## The idea

Most dashboards are closed systems. This one is a framework first. Every widget is a self-contained folder with three files and a clear contract. You describe what you want to a language model, hand it the guide, and it writes a working widget.

```
widgets/widget-your-name/
├── manifest.json   ← what the widget is: settings, refresh, location, appearance
├── data.js         ← HTML + CSS + JS bundle
└── api.py          ← optional Flask backend (auto-discovered, no registration needed)
```

The server reads `manifest.json` at startup. Settings are saved and injected automatically as `data-*` attributes. You never touch server code to add a widget.

---

## Quick start

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5003` and follow the setup wizard.

---

## Building a widget with an LLM

1. Open [`widgets/README.md`](widgets/README.md) — the complete widget creation guide
2. Paste it into your LLM of choice along with a description of what you want
3. Drop the output into `widgets/widget-your-name/`
4. Restart the server — the widget appears automatically

The guide covers the full contract: manifest field types, the JS class pattern, how `data-*` attributes are injected, and how to write a backend route if the widget needs to fetch data.

---

## Included widgets

| Widget | Description |
|--------|-------------|
| `widget-apple-clock` | Digital clock with timezone and city |
| `widget-apple-clock-analogue-dark` | Analog clock, dark dial |
| `widget-braun-clock` | Braun-styled analog clock with date |
| `widget-nothing-watch` | Nothing Phone–style dot-grid watch face |
| `widget-apple-pomodoro` | 25-minute pomodoro timer |
| `widget-apple-calendar` | Current day and date |
| `widget-apple-calendar-2` | Full month calendar grid |
| `widget-google-calendar` | Embedded Google Calendar |
| `widget-apple-weather` | Temperature, conditions, high/low |
| `widget-google-weather` | Hourly forecast with rain % (up to 12h) |
| `widget-google-weather-alerts` | Weather alert carousel with severity |
| `widget-google-wind` | Wind speed, gust, direction + compass |
| `widget-apple-sunrise` | Sunrise/sunset with animated sun arc |
| `widget-apple-bbc` | BBC News with images and live indicator |
| `widget-ap-news` | AP News grouped by category |
| `widget-kagi-news` | Kagi News in Stories format — full-bleed, tap to advance |
| `widget-apple-unsplashed` | Rotating Unsplash photography |
| `widget-mondrian` | Procedural Mondrian art generator |
| `widget-apple-sunrise` | Sunrise/sunset times with animated arc |

---

## Settings

Access via the gear icon in the dashboard header.

- **Background** — gradient presets, custom CSS, or wallpaper gallery (drop images into `static/Wallpapers/`)
- **Live wallpapers** — 199 Apple TV aerial videos, downloaded on demand
- **Widget style editor** — theme presets, color, opacity, blur, radius, border, shadow, font, refresh interval, raw CSS override
- **Location** — set once, shared by weather, wind, alerts, and sunrise widgets

---

## Multi-device

Each browser registers as a separate device with its own name, layout, and settings. Devices are auto-named (`calm-sun`, `lunar-willow`). Switch via `/switch/<device_id>`.

---

## Requirements

- Python 3.9+
- `pip install -r requirements.txt`
- [ffmpeg](https://ffmpeg.org/) — optional, required for aerial video downloads (`brew install ffmpeg`)

---

## Disclaimer

This repository is for educational purposes only. All widgets, integrations, and techniques shown here are intended to demonstrate how to build with publicly available APIs and tools. Use responsibly and in accordance with the terms of service of any third-party services used.

All brand names, trademarks, service marks, logos, and trade names referenced in this project (including but not limited to Apple, Google, BBC, AP News, Kagi, Unsplash, Braun, and Nothing) are the property of their respective owners. Their use here is purely for identification purposes and does not imply any affiliation with or endorsement by those companies.

---

## License

MIT
