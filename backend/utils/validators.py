"""Request validation helpers + standard JSON response envelopes."""
from flask import jsonify


def success_response(data=None, status=200, **extra):
    body = {"success": True, "data": data}
    body.update(extra)
    return jsonify(body), status


def error_response(message, status=400, errors=None):
    body = {"success": False, "error": message}
    if errors:
        body["errors"] = errors
    return jsonify(body), status


def require_fields(payload, fields):
    """Returns a list of missing/blank required field names."""
    if not isinstance(payload, dict):
        return list(fields)
    missing = []
    for field in fields:
        value = payload.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            missing.append(field)
    return missing


def is_positive_number(value):
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def is_non_negative_number(value):
    try:
        return float(value) >= 0
    except (TypeError, ValueError):
        return False


def is_positive_int(value):
    try:
        return int(value) > 0 and float(value) == int(value)
    except (TypeError, ValueError):
        return False
