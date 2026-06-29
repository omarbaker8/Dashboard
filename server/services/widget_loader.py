"""
Widget loader: reads data.js base definitions from disk and enriches them
with manifest.json metadata where present.
"""
import json
import re
from pathlib import Path
from server.config import WIDGETS_DIR

_WIDGETS_PATH = Path(WIDGETS_DIR)
_MODULE_EXPORTS_RE = re.compile(r'^module\.exports\s*=\s*', re.MULTILINE)


def get_base_widgets():
    """Read all widget base definitions from data.js files."""
    widgets = []
    for wdir in sorted(_WIDGETS_PATH.iterdir()):
        if not wdir.is_dir() or wdir.name.startswith('_'):
            continue
        data_js = wdir / 'data.js'
        if not data_js.exists():
            continue
        try:
            raw = data_js.read_text(encoding='utf-8').strip()
            raw = _MODULE_EXPORTS_RE.sub('', raw, count=1)
            if raw.endswith(';'):
                raw = raw[:-1]
            widget = json.loads(raw)
            widgets.append(widget)
        except Exception as e:
            print(f"[widget-loader] skipping {data_js}: {e}")
    return widgets


def load_manifest(widget_id):
    """Load manifest.json for a widget ID. Returns {} if not found."""
    manifest_path = _WIDGETS_PATH / widget_id / 'manifest.json'
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding='utf-8'))
        except Exception as e:
            print(f"[widget-loader] manifest parse error for {widget_id}: {e}")
    return {}


def save_base_widget(widget):
    """Persist a widget definition to its data.js file."""
    wdir = _WIDGETS_PATH / widget['id']
    wdir.mkdir(exist_ok=True)
    (wdir / 'data.js').write_text(
        f"module.exports = {json.dumps(widget, indent=4, ensure_ascii=False)};\n",
        encoding='utf-8',
    )
