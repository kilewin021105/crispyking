"""Runtime-editable app settings, stored as key/value rows in `settings`.

This is what makes tax rate/currency/business info *flexible*: an admin can
change them from the Settings tab and every part of the app (order totals,
receipts, branding) picks up the new value immediately — no .env edit, no
restart. `config.py` / `.env` still supply the bootstrap defaults used the
very first time the table is seeded (see database/seed.sql).
"""
import db

DEFAULTS = {
    "business_name": "Crispy King",
    "currency_symbol": "$",
    "tax_rate": "0.10",
    "business_phone": "",
    "business_address": "",
    "receipt_footer": "Thank you for your order!",
}


def get_all_settings():
    """Returns every setting as a flat {key: value} dict, defaults filled in
    for any key not yet present in the table."""
    rows = db.query_all("SELECT setting_key, setting_value FROM settings")
    merged = dict(DEFAULTS)
    merged.update({r["setting_key"]: r["setting_value"] for r in rows})
    return merged


def get_setting(key, default=None):
    row = db.query_one(
        "SELECT setting_value FROM settings WHERE setting_key = %s", (key,)
    )
    if row:
        return row["setting_value"]
    return DEFAULTS.get(key, default)


def get_tax_rate(fallback=0.10):
    """Tax rate as a float fraction (e.g. 0.10 == 10%)."""
    try:
        return float(get_setting("tax_rate", fallback))
    except (TypeError, ValueError):
        return fallback


def update_settings(updates: dict):
    """Upsert a batch of {key: value} pairs. Unknown keys are rejected so the
    table can't accumulate typos from a bad client payload."""
    unknown = [k for k in updates if k not in DEFAULTS]
    if unknown:
        raise ValueError(f"Unknown setting(s): {', '.join(unknown)}")

    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        for key, value in updates.items():
            cursor.execute(
                """INSERT INTO settings (setting_key, setting_value)
                   VALUES (%s, %s)
                   ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)""",
                (key, str(value)),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return get_all_settings()
