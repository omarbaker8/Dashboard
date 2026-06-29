import importlib.util
from pathlib import Path


def register_blueprints(app):
    # System blueprints
    from .layout import bp as layout_bp
    from .devices import bp as devices_bp
    from .media import bp as media_bp
    from .location import bp as location_bp
    for bp in (layout_bp, devices_bp, media_bp, location_bp):
        app.register_blueprint(bp)

    # Widget-specific blueprints — auto-discovered from widgets/*/api.py
    widgets_dir = Path(app.config['BASE_DIR']) / 'widgets'
    for api_path in sorted(widgets_dir.glob('*/api.py')):
        blueprint_name = api_path.parent.name.replace('-', '_')
        spec = importlib.util.spec_from_file_location(blueprint_name, api_path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            app.register_blueprint(module.bp)
        except Exception as e:
            print(f"[blueprints] failed to load {api_path}: {e}")
