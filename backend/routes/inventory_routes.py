"""Inventory module: stock levels + restock/adjustment tracking."""
from flask import Blueprint, request

import db
from utils.validators import error_response, require_fields, success_response

inventory_bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")

VALID_ADJUST_TYPES = {"adjustment", "waste"}


@inventory_bp.get("")
def list_inventory():
    """Stock level per product, flagged as low-stock when at/under reorder level."""
    rows = db.query_all(
        """SELECT product_id, sku, name, category, stock_quantity, reorder_level,
                  (stock_quantity <= reorder_level) AS low_stock
           FROM products
           WHERE is_active = 1
           ORDER BY low_stock DESC, name"""
    )
    for r in rows:
        r["low_stock"] = bool(r["low_stock"])
    return success_response(rows, count=len(rows))


@inventory_bp.get("/low-stock")
def low_stock():
    rows = db.query_all(
        """SELECT product_id, sku, name, category, stock_quantity, reorder_level
           FROM products
           WHERE is_active = 1 AND stock_quantity <= reorder_level
           ORDER BY stock_quantity ASC"""
    )
    return success_response(rows, count=len(rows))


@inventory_bp.get("/<int:product_id>/history")
def product_history(product_id):
    product = db.query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if not product:
        return error_response("Product not found", 404)

    history = db.query_all(
        """SELECT * FROM inventory_transactions
           WHERE product_id = %s ORDER BY created_at DESC LIMIT 100""",
        (product_id,),
    )
    return success_response({"product": product, "history": history})


@inventory_bp.post("/restock")
def restock():
    """Body: { "product_id": 1, "quantity": 20, "note": "weekly delivery" }"""
    payload = request.get_json(silent=True) or {}
    missing = require_fields(payload, ["product_id", "quantity"])
    if missing:
        return error_response(f"Missing required fields: {', '.join(missing)}", 422)

    try:
        product_id = int(payload["product_id"])
        quantity = int(payload["quantity"])
    except (TypeError, ValueError):
        return error_response("product_id and quantity must be integers", 422)

    if quantity <= 0:
        return error_response("quantity must be a positive integer", 422)

    product = db.query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if not product:
        return error_response("Product not found", 404)

    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE products SET stock_quantity = stock_quantity + %s WHERE product_id = %s",
            (quantity, product_id),
        )
        cursor.execute(
            """INSERT INTO inventory_transactions
               (product_id, change_qty, transaction_type, note)
               VALUES (%s, %s, 'restock', %s)""",
            (product_id, quantity, payload.get("note", "Manual restock")),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        return error_response(f"Could not restock: {exc}", 500)
    finally:
        conn.close()

    updated = db.query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    return success_response(updated)


@inventory_bp.post("/adjust")
def adjust():
    """Body: { "product_id": 1, "change_qty": -3, "type": "waste", "note": "spoiled" }
    change_qty may be negative (waste/loss) or positive (correction)."""
    payload = request.get_json(silent=True) or {}
    missing = require_fields(payload, ["product_id", "change_qty"])
    if missing:
        return error_response(f"Missing required fields: {', '.join(missing)}", 422)

    try:
        product_id = int(payload["product_id"])
        change_qty = int(payload["change_qty"])
    except (TypeError, ValueError):
        return error_response("product_id and change_qty must be integers", 422)

    if change_qty == 0:
        return error_response("change_qty must not be zero", 422)

    txn_type = payload.get("type", "adjustment")
    if txn_type not in VALID_ADJUST_TYPES:
        return error_response(f"type must be one of {sorted(VALID_ADJUST_TYPES)}", 422)

    product = db.query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if not product:
        return error_response("Product not found", 404)

    new_qty = product["stock_quantity"] + change_qty
    if new_qty < 0:
        return error_response(
            f"Adjustment would result in negative stock (current: {product['stock_quantity']})", 409
        )

    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE products SET stock_quantity = %s WHERE product_id = %s",
            (new_qty, product_id),
        )
        cursor.execute(
            """INSERT INTO inventory_transactions
               (product_id, change_qty, transaction_type, note)
               VALUES (%s, %s, %s, %s)""",
            (product_id, change_qty, txn_type, payload.get("note")),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        return error_response(f"Could not adjust stock: {exc}", 500)
    finally:
        conn.close()

    updated = db.query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    return success_response(updated)
