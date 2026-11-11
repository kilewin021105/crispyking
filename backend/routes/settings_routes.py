"""Settings module: business name, currency, tax rate, receipt info.

Like the rest of this API, these routes have no server-side auth check —
that's consistent with every other blueprint here (menu, orders, suppliers
all have none either). The Settings *tab* in the POS frontend is hidden
from non-admin users client-side; wiring up real authentication for the
whole API is a bigger, separate change.
"""
from flask import Blueprint, request

from utils.settings import DEFAULTS, get_all_settings, update_settings
from utils.validators import error_response, success_response

settings_bp = Blueprint("settings", __name__, url_prefix="/api/settings")


@settings_bp.get("")
def get_settings():
    return success_response(get_all_settings())


@settings_bp.put("")
def put_settings():
    """Body: any subset of the known setting keys, e.g.
    { "business_name": "Crispy King", "tax_rate": "0.12" }"""
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict) or not payload:
        return error_response("Body must be a non-empty object of setting key/value pairs", 422)

    if "tax_rate" in payload:
        try:
            rate = float(payload["tax_rate"])
        except (TypeError, ValueError):
            return error_response("tax_rate must be a number between 0 and 1", 422)
        if rate < 0 or rate > 1:
            return error_response("tax_rate must be between 0 and 1 (e.g. 0.10 for 10%)", 422)

    try:
        updated = update_settings(payload)
    except ValueError as exc:
        return error_response(str(exc), 422)

    return success_response(updated)


@settings_bp.get("/defaults")
def get_defaults():
    """What each setting resets to — used by the Settings tab's "Reset" action."""
    return success_response(DEFAULTS)
