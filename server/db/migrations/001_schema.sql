-- Dashboard schema — idempotent (IF NOT EXISTS throughout)

CREATE TABLE IF NOT EXISTS devices (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL CHECK(type IN ('laptop', 'tablet')),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-device key/value config (background, blur, dim, default location, etc.)
CREATE TABLE IF NOT EXISTS device_config (
    device_id   TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    PRIMARY KEY (device_id, key)
);

-- Per-device widget layout + settings
-- css    → assembled outer CSS (appearance values)
-- extra  → JSON blob of all behaviour settings (lat, lng, timezone, categories, etc.)
CREATE TABLE IF NOT EXISTS device_widgets (
    device_id   TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    widget_id   TEXT NOT NULL,
    x           INTEGER NOT NULL,
    y           INTEGER NOT NULL,
    w           INTEGER NOT NULL,
    h           INTEGER NOT NULL,
    css         TEXT NOT NULL DEFAULT '',
    extra       TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (device_id, widget_id)
);

-- Migration tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  INTEGER NOT NULL DEFAULT (unixepoch())
);
