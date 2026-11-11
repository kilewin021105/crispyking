"""Ingredients module: raw materials/supplies used to MAKE the menu — oil,
flour, wrappers, gas, packaging, etc. Separate from the Inventory module,
which tracks finished, sellable products. Mirrors inventory_routes.py's
restock/adjust pattern, with its own transaction log for audit history."""
from flask import Blueprint, request

import db
from utils.validators import (
    error_response,
    is_non_negative_number,
    require_fields,
    success_response,
)

ingredients_bp = Blueprint("ingredients", __name__, url_prefix="/api/ingredients")

VALID_ADJUST_TYPES = {"adjustment", "waste", "usage"}


@ingredients_bp.get("")
def list_ingredients():
    """GET /api/ingredients?search= — stock level per ingredient, flagged
    low-stock when at/under reorder level."""
    search = request.args.get("search")
    sql = """SELECT i.*, s.name AS supplier_name,
                    (i.stock_quantity <= i.reorder_level) AS low_stock
             FROM ingredients i
             LEFT JOIN suppliers s ON s.supplier_id = i.supplier_id
             WHERE i.is_active = 1"""
    params = []
    if search:
        sql += " AND i.name LIKE %s"
        params.append(f"%{search}%")
    sql += " ORDER BY low_stock DESC, i.name"

    rows = db.query_all(sql, params)
    for r in rows:
        r["low_stock"] = bool(r["low_stock"])
        r["stock_quantity"] = float(r["stock_quantity"])
        r["reorder_level"] = float(r["reorder_level"])
        r["cost_per_unit"] = float(r["cost_per_unit"])
    return success_response(rows, count=len(rows))


@ingredients_bp.get("/low-stock")
def low_stock():
    rows = db.query_all(
        """SELECT ingredient_id, name, unit, stock_quantity, reorder_level
           FROM ingredients
           WHERE is_active = 1 AND stock_quantity <= reorder_level
           ORDER BY stock_quantity ASC"""
    )
    for r in rows:
        r["stock_quantity"] = float(r["stock_quantity"])
        r["reorder_level"] = float(r["reorder_level"])
    return success_response(rows, count=len(rows))


@ingredients_bp.get("/value")
def ingredients_value():
    """Current raw-materials valuation — units on hand x cost per unit."""
    rows = db.query_all(
        """SELECT ingredient_id, name, unit, stock_quantity, cost_per_unit,
                  (stock_quantity * cost_per_unit) AS stock_value
           FROM ingredients
           WHERE is_active = 1
           ORDER BY stock_value DESC"""
    )
    total = 0.0
    for r in rows:
        r["stock_quantity"] = float(r["stock_quantity"])
        r["cost_per_unit"] = float(r["cost_per_unit"])
        r["stock_value"] = float(r["stock_value"])
        total += r["stock_value"]
    return success_response({"ingredients": rows, "total_stock_value": round(total, 2)})


@ingredients_bp.get("/<int:ingredient_id>/history")
def ingredient_history(ingredient_id):
    ingredient = db.query_one("SELECT * FROM ingredients WHERE ingredient_id = %s", (ingredient_id,))
    if not ingredient:
        return error_response("Ingredient not found", 404)

    history = db.query_all(
        """SELECT * FROM ingredient_transactions
           WHERE ingredient_id = %s ORDER BY created_at DESC LIMIT 100""",
        (ingredient_id,),
    )
    for h in history:
        h["change_qty"] = float(h["change_qty"])
    return success_response({"ingredient": ingredient, "history": history})


@ingredients_bp.post("")
def create_ingredient():
    """Add a new ingredient/supply — the "and etc" case: the list of things
    needed to make the food is never final, so this is a free-form add,
    not a fixed enum."""
    payload = request.get_json(silent=True) or {}
    missing = require_fields(payload, ["name"])
    if missing:
        return error_response(f"Missing required fields: {', '.join(missing)}", 422)

    for field in ("stock_quantity", "reorder_level", "cost_per_unit"):
        if field in payload and not is_non_negative_number(payload[field]):
            return error_response(f"{field} must be a non-negative number", 422)

    try:
        ingredient_id, _ = db.execute(
            """INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, cost_per_unit, supplier_id)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                payload["name"].strip(),
                payload.get("unit", "pcs"),
                payload.get("stock_quantity", 0),
                payload.get("reorder_level", 0),
                payload.get("cost_per_unit", 0),
                payload.get("supplier_id"),
            ),
        )
    except Exception as exc:  # duplicate name, etc.
        return error_response(f"Could not create ingredient: {exc}", 400)

    ingredient = db.query_one("SELECT * FROM ingredients WHERE ingredient_id = %s", (ingredient_id,))
    return success_response(ingredient, 201)


@ingredients_bp.put("/<int:ingredient_id>")
def update_ingredient(ingredient_id):
    existing = db.query_one("SELECT * FROM ingredients WHERE ingredient_id = %s", (ingredient_id,))
    if not existing:
        return error_response("Ingredient not found", 404)

    payload = request.get_json(silent=True) or {}
    for field in ("stock_quantity", "reorder_level", "cost_per_unit"):
        if field in payload and not is_non_negative_number(payload[field]):
            return error_response(f"{field} must be a non-negative number", 422)

    editable_fields = ["name", "unit", "reorder_level", "cost_per_unit", "supplier_id", "is_active"]
    updates = {k: v for k, v in payload.items() if k in editable_fields}
    if not updates:
        return error_response("No valid fields to update", 422)

    set_clause = ", ".join(f"{field} = %s" for field in updates)
    params = list(updates.values()) + [ingredient_id]
    db.execute(f"UPDATE ingredients SET {set_clause} WHERE ingredient_id = %s", params)

    ingredient = db.query_one("SELECT * FROM ingredients WHERE ingredient_id = %s", (ingredient_id,))
    return success_response(ingredient)


@ingredients_bp.delete("/<int:ingredient_id>")
def delete_ingredient(ingredient_id):
    """Soft delete: mark inactive instead of removing history-linked rows."""
    existing = db.query_one("SELECT * FROM ingredients WHERE ingredient_id = %s", (ingredient_id,))
    if not existing:
        return error_response("Ingredient not found", 404)

    db.execute("UPDATE ingredients SET is_active = 0 WHERE ingredient_id = %s", (ingredient_id,))
    return success_response({"ingredient_id": ingredient_id, "is_active": False})


@ingredients_bp.post("/restock")
def restock():
    """Body: { "ingredient_id": 1, "quantity": 10, "note": "weekly delivery" }"""
    payload = request.get_json(silent=True) or {}
    missing = require_fields(payload, ["ingredient_id", "quantity"])
    if missing:
        return error_response(f"Missing required fields: {', '.join(missing)}", 422)

    try:
        ingredient_id = int(payload["ingredient_id"])
    except (TypeError, ValueError):
        return error_response("ingredient_id must be an integer", 422)

    if not is_non_negative_number(payload["quantity"]) or float(payload["quantity"]) <= 0:
        return error_response("quantity must be a positive number", 422)
    quantity = float(payload["quantity"])

    ingredient = db.query_one("SELECT * FROM ingredients WHERE ingredient_id = %s", (ingredient_id,))
    if not ingredient:
        return error_response("Ingredient not found", 404)

    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE ingredients SET stock_quantity = stock_quantity + %s WHERE ingredient_id = %s",
            (quantity, ingredient_id),
        )
        cursor.execute(
            """INSERT INTO ingredient_transactions (ingredient_id, change_qty, transaction_type, note)
               VALUES (%s, %s, 'restock', %s)""",
            (ingredient_id, quantity, payload.get("note", "Manual restock")),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        return error_response(f"Could not restock: {exc}", 500)
    finally:
        conn.close()

    updated = db.query_one("SELECT * FROM ingredients WHERE ingredient_id = %s", (ingredient_id,))
    return success_response(updated)


@ingredients_bp.post("/adjust")
def adjust():
    """Body: { "ingredient_id": 1, "change_qty": -2.5, "type": "usage", "note": "..." }
    change_qty may be negative (usage/waste) or positive (correction)."""
    payload = request.get_json(silent=True) or {}
    missing = require_fields(payload, ["ingredient_id", "change_qty"])
    if missing:
        return error_response(f"Missing required fields: {', '.join(missing)}", 422)

    try:
        ingredient_id = int(payload["ingredient_id"])
        change_qty = float(payload["change_qty"])
    except (TypeError, ValueError):
        return error_response("ingredient_id must be an integer and change_qty a number", 422)

    if change_qty == 0:
        return error_response("change_qty must not be zero", 422)

    txn_type = payload.get("type", "adjustment")
    if txn_type not in VALID_ADJUST_TYPES:
        return error_response(f"type must be one of {sorted(VALID_ADJUST_TYPES)}", 422)

    ingredient = db.query_one("SELECT * FROM ingredients WHERE ingredient_id = %s", (ingredient_id,))
    if not ingredient:
        return error_response("Ingredient not found", 404)

    new_qty = float(ingredient["stock_quantity"]) + change_qty
    if new_qty < 0:
        return error_response(
            f"Adjustment would result in negative stock (current: {ingredient['stock_quantity']})", 409
        )

    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE ingredients SET stock_quantity = %s WHERE ingredient_id = %s",
            (new_qty, ingredient_id),
        )
        cursor.execute(
            """INSERT INTO ingredient_transactions (ingredient_id, change_qty, transaction_type, note)
               VALUES (%s, %s, %s, %s)""",
            (ingredient_id, change_qty, txn_type, payload.get("note")),
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        return error_response(f"Could not adjust stock: {exc}", 500)
    finally:
        conn.close()

    updated = db.query_one("SELECT * FROM ingredients WHERE ingredient_id = %s", (ingredient_id,))
    return success_response(updated)
