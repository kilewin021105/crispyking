"""Suppliers feeding the Menu / Inventory modules."""
from flask import Blueprint, request

import db
from utils.validators import error_response, require_fields, success_response

suppliers_bp = Blueprint("suppliers", __name__, url_prefix="/api/suppliers")


@suppliers_bp.get("")
def list_suppliers():
    suppliers = db.query_all("SELECT * FROM suppliers ORDER BY name")
    return success_response(suppliers, count=len(suppliers))


@suppliers_bp.get("/<int:supplier_id>")
def get_supplier(supplier_id):
    supplier = db.query_one("SELECT * FROM suppliers WHERE supplier_id = %s", (supplier_id,))
    if not supplier:
        return error_response("Supplier not found", 404)

    products = db.query_all(
        "SELECT product_id, name, price, stock_quantity FROM products WHERE supplier_id = %s",
        (supplier_id,),
    )
    supplier["products"] = products
    return success_response(supplier)


@suppliers_bp.post("")
def create_supplier():
    payload = request.get_json(silent=True) or {}
    missing = require_fields(payload, ["name"])
    if missing:
        return error_response(f"Missing required fields: {', '.join(missing)}", 422)

    supplier_id, _ = db.execute(
        """INSERT INTO suppliers (name, contact_person, phone, email, address)
           VALUES (%s, %s, %s, %s, %s)""",
        (
            payload["name"].strip(),
            payload.get("contact_person"),
            payload.get("phone"),
            payload.get("email"),
            payload.get("address"),
        ),
    )
    supplier = db.query_one("SELECT * FROM suppliers WHERE supplier_id = %s", (supplier_id,))
    return success_response(supplier, 201)


@suppliers_bp.put("/<int:supplier_id>")
def update_supplier(supplier_id):
    existing = db.query_one("SELECT * FROM suppliers WHERE supplier_id = %s", (supplier_id,))
    if not existing:
        return error_response("Supplier not found", 404)

    payload = request.get_json(silent=True) or {}
    editable = ["name", "contact_person", "phone", "email", "address"]
    updates = {k: v for k, v in payload.items() if k in editable}
    if not updates:
        return error_response("No valid fields to update", 422)

    set_clause = ", ".join(f"{field} = %s" for field in updates)
    params = list(updates.values()) + [supplier_id]
    db.execute(f"UPDATE suppliers SET {set_clause} WHERE supplier_id = %s", params)

    supplier = db.query_one("SELECT * FROM suppliers WHERE supplier_id = %s", (supplier_id,))
    return success_response(supplier)


@suppliers_bp.delete("/<int:supplier_id>")
def delete_supplier(supplier_id):
    existing = db.query_one("SELECT * FROM suppliers WHERE supplier_id = %s", (supplier_id,))
    if not existing:
        return error_response("Supplier not found", 404)

    try:
        db.execute("DELETE FROM suppliers WHERE supplier_id = %s", (supplier_id,))
    except Exception as exc:
        return error_response(f"Cannot delete supplier: {exc}", 409)

    return success_response({"supplier_id": supplier_id, "deleted": True})
