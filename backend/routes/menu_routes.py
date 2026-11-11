"""Menu module: products (items + prices)."""
from flask import Blueprint, request

import db
from utils.validators import (
    error_response,
    is_non_negative_number,
    require_fields,
    success_response,
)

menu_bp = Blueprint("menu", __name__, url_prefix="/api/menu")


@menu_bp.get("")
def list_products():
    """GET /api/menu?category=&search=&active_only=true"""
    category = request.args.get("category")
    search = request.args.get("search")
    active_only = request.args.get("active_only", "true").lower() != "false"

    sql = """SELECT p.*, s.name AS supplier_name
              FROM products p
              LEFT JOIN suppliers s ON s.supplier_id = p.supplier_id
              WHERE 1=1"""
    params = []

    if active_only:
        sql += " AND p.is_active = 1"
    if category:
        sql += " AND p.category = %s"
        params.append(category)
    if search:
        sql += " AND (p.name LIKE %s OR p.description LIKE %s)"
        like = f"%{search}%"
        params.extend([like, like])

    sql += " ORDER BY p.category, p.name"
    products = db.query_all(sql, params)
    return success_response(products, count=len(products))


@menu_bp.get("/categories")
def list_categories():
    rows = db.query_all(
        "SELECT DISTINCT category FROM products WHERE is_active = 1 ORDER BY category"
    )
    return success_response([r["category"] for r in rows])


@menu_bp.get("/<int:product_id>")
def get_product(product_id):
    product = db.query_one(
        """SELECT p.*, s.name AS supplier_name
           FROM products p
           LEFT JOIN suppliers s ON s.supplier_id = p.supplier_id
           WHERE p.product_id = %s""",
        (product_id,),
    )
    if not product:
        return error_response("Product not found", 404)
    return success_response(product)


@menu_bp.post("")
def create_product():
    """Add a new menu item."""
    payload = request.get_json(silent=True) or {}

    missing = require_fields(payload, ["name", "price", "category"])
    if missing:
        return error_response(f"Missing required fields: {', '.join(missing)}", 422)

    if not is_non_negative_number(payload.get("price")):
        return error_response("price must be a non-negative number", 422)

    cost_price = payload.get("cost_price", 0)
    if not is_non_negative_number(cost_price):
        return error_response("cost_price must be a non-negative number", 422)

    stock_quantity = payload.get("stock_quantity", 0)
    try:
        stock_quantity = int(stock_quantity)
        if stock_quantity < 0:
            raise ValueError
    except (TypeError, ValueError):
        return error_response("stock_quantity must be a non-negative integer", 422)

    supplier_id = payload.get("supplier_id")
    if supplier_id is not None:
        supplier = db.query_one(
            "SELECT supplier_id FROM suppliers WHERE supplier_id = %s", (supplier_id,)
        )
        if not supplier:
            return error_response("supplier_id does not exist", 422)

    try:
        product_id, _ = db.execute(
            """INSERT INTO products
               (sku, name, description, category, price, cost_price,
                supplier_id, stock_quantity, reorder_level, is_active)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                payload.get("sku"),
                payload["name"].strip(),
                payload.get("description", ""),
                payload["category"].strip(),
                payload["price"],
                cost_price,
                supplier_id,
                stock_quantity,
                payload.get("reorder_level", 10),
                bool(payload.get("is_active", True)),
            ),
        )
    except Exception as exc:  # duplicate SKU, etc.
        return error_response(f"Could not create product: {exc}", 400)

    product = db.query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    return success_response(product, 201)


@menu_bp.put("/<int:product_id>")
def update_product(product_id):
    existing = db.query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if not existing:
        return error_response("Product not found", 404)

    payload = request.get_json(silent=True) or {}
    if "price" in payload and not is_non_negative_number(payload["price"]):
        return error_response("price must be a non-negative number", 422)

    editable_fields = [
        "sku", "name", "description", "category", "price", "cost_price",
        "supplier_id", "stock_quantity", "reorder_level", "is_active",
    ]
    updates = {k: v for k, v in payload.items() if k in editable_fields}
    if not updates:
        return error_response("No valid fields to update", 422)

    set_clause = ", ".join(f"{field} = %s" for field in updates)
    params = list(updates.values()) + [product_id]
    db.execute(f"UPDATE products SET {set_clause} WHERE product_id = %s", params)

    product = db.query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    return success_response(product)


@menu_bp.delete("/<int:product_id>")
def delete_product(product_id):
    """Soft delete: mark inactive instead of removing history-linked rows."""
    existing = db.query_one("SELECT * FROM products WHERE product_id = %s", (product_id,))
    if not existing:
        return error_response("Product not found", 404)

    db.execute("UPDATE products SET is_active = 0 WHERE product_id = %s", (product_id,))
    return success_response({"product_id": product_id, "is_active": False})
