"""Minimal cashier/admin login used by the POS screen."""
from flask import Blueprint, request
from werkzeug.security import check_password_hash

import db
from utils.validators import error_response, require_fields, success_response

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    missing = require_fields(payload, ["username", "password"])
    if missing:
        return error_response(f"Missing required fields: {', '.join(missing)}", 422)

    user = db.query_one(
        "SELECT * FROM users WHERE username = %s", (payload["username"].strip(),)
    )
    if not user or not check_password_hash(user["password_hash"], payload["password"]):
        return error_response("Invalid username or password", 401)

    return success_response(
        {
            "user_id": user["user_id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role": user["role"],
        }
    )
