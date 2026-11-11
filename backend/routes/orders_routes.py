"""Orders module: dine-in / takeout order lifecycle.

Business logic lives here:
  - server computes prices/totals (never trusts client-sent totals)
  - stock is validated and decremented atomically when an order is placed
  - inventory_transactions records every stock movement for the Reports module
  - cancelling a pending order restocks its items
"""
from flask import Blueprint, request

import db
from utils.settings import get_tax_rate
from utils.validators import error_response, is_positive_int, require_fields, success_response

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")

VALID_ORDER_TYPES = {"dine-in", "takeout"}
VALID_STATUSES = ["pending", "preparing", "ready", "completed", "cancelled"]
VALID_PAYMENT_METHODS = {"cash", "card", "mobile"}


def _order_with_items(order_id):
    order = db.query_one("SELECT * FROM orders WHERE order_id = %s", (order_id,))
    if not order:
        return None
    order["items"] = db.query_all(
        """SELECT oi.*, p.name AS product_name
           FROM order_items oi
           JOIN products p ON p.product_id = oi.product_id
           WHERE oi.order_id = %s""",
        (order_id,),
    )
    return order


@orders_bp.get("")
def list_orders():
    """GET /api/orders?status=&order_type=&limit=50"""
    status = request.args.get("status")
    order_type = request.args.get("order_type")
    limit = min(int(request.args.get("limit", 50)), 200)

    sql = """SELECT o.*,
                    (SELECT COALESCE(SUM(oi.quantity), 0)
                     FROM order_items oi WHERE oi.order_id = o.order_id) AS item_count
             FROM orders o WHERE 1=1"""
    params = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if order_type:
        sql += " AND order_type = %s"
        params.append(order_type)
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    orders = db.query_all(sql, params)
    return success_response(orders, count=len(orders))


@orders_bp.get("/<int:order_id>")
def get_order(order_id):
    order = _order_with_items(order_id)
    if not order:
        return error_response("Order not found", 404)
    return success_response(order)


@orders_bp.post("")
def create_order():
    """
    Body: {
      "order_type": "dine-in" | "takeout",
      "customer_name": "...",        (optional)
      "table_number": "...",          (optional, dine-in)
      "cashier_id": 1,                 (optional)
      "payment_method": "cash",
      "items": [{ "product_id": 1, "quantity": 2 }, ...]
    }
    """
    payload = request.get_json(silent=True) or {}

    missing = require_fields(payload, ["order_type", "items"])
    if missing:
        return error_response(f"Missing required fields: {', '.join(missing)}", 422)

    order_type = payload["order_type"]
    if order_type not in VALID_ORDER_TYPES:
        return error_response(f"order_type must be one of {sorted(VALID_ORDER_TYPES)}", 422)

    payment_method = payload.get("payment_method", "cash")
    if payment_method not in VALID_PAYMENT_METHODS:
        return error_response(f"payment_method must be one of {sorted(VALID_PAYMENT_METHODS)}", 422)

    items = payload.get("items")
    if not isinstance(items, list) or len(items) == 0:
        return error_response("items must be a non-empty array", 422)

    for item in items:
        if not isinstance(item, dict) or not is_positive_int(item.get("product_id")) \
                or not is_positive_int(item.get("quantity")):
            return error_response(
                "each item requires a positive integer product_id and quantity", 422
            )

    tax_rate = get_tax_rate()  # read before opening the transaction below

    conn = db.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        # Lock and validate every product row within the transaction
        subtotal = 0
        resolved_items = []
        for item in items:
            cursor.execute(
                "SELECT * FROM products WHERE product_id = %s FOR UPDATE",
                (item["product_id"],),
            )
            product = cursor.fetchone()
            if not product:
                conn.rollback()
                return error_response(f"Product {item['product_id']} not found", 422)
            if not product["is_active"]:
                conn.rollback()
                return error_response(f"Product '{product['name']}' is not available", 422)

            quantity = int(item["quantity"])
            if product["stock_quantity"] < quantity:
                conn.rollback()
                return error_response(
                    f"Insufficient stock for '{product['name']}' "
                    f"(available: {product['stock_quantity']}, requested: {quantity})",
                    409,
                )

            line_total = float(product["price"]) * quantity
            subtotal += line_total
            resolved_items.append(
                {"product": product, "quantity": quantity, "unit_price": product["price"], "line_total": line_total}
            )

        tax_amount = round(subtotal * tax_rate, 2)
        total_amount = round(subtotal + tax_amount, 2)

        cursor.execute(
            """INSERT INTO orders
               (order_type, status, customer_name, table_number, cashier_id,
                payment_method, subtotal, tax_amount, total_amount)
               VALUES (%s, 'pending', %s, %s, %s, %s, %s, %s, %s)""",
            (
                order_type,
                payload.get("customer_name"),
                payload.get("table_number"),
                payload.get("cashier_id"),
                payment_method,
                round(subtotal, 2),
                tax_amount,
                total_amount,
            ),
        )
        order_id = cursor.lastrowid

        for entry in resolved_items:
            product = entry["product"]
            cursor.execute(
                """INSERT INTO order_items (order_id, product_id, quantity, unit_price, line_total)
                   VALUES (%s, %s, %s, %s, %s)""",
                (order_id, product["product_id"], entry["quantity"], entry["unit_price"], entry["line_total"]),
            )
            cursor.execute(
                "UPDATE products SET stock_quantity = stock_quantity - %s WHERE product_id = %s",
                (entry["quantity"], product["product_id"]),
            )
            cursor.execute(
                """INSERT INTO inventory_transactions
                   (product_id, change_qty, transaction_type, reference_order_id, note)
                   VALUES (%s, %s, 'sale', %s, %s)""",
                (product["product_id"], -entry["quantity"], order_id, f"Order #{order_id}"),
            )

        conn.commit()
    except Exception as exc:
        conn.rollback()
        return error_response(f"Could not create order: {exc}", 500)
    finally:
        conn.close()

    return success_response(_order_with_items(order_id), 201)


@orders_bp.put("/<int:order_id>/status")
def update_order_status(order_id):
    """Advance/cancel an order. Cancelling restocks reserved inventory."""
    order = db.query_one("SELECT * FROM orders WHERE order_id = %s", (order_id,))
    if not order:
        return error_response("Order not found", 404)

    payload = request.get_json(silent=True) or {}
    new_status = payload.get("status")
    if new_status not in VALID_STATUSES:
        return error_response(f"status must be one of {VALID_STATUSES}", 422)

    if order["status"] in ("completed", "cancelled"):
        return error_response(f"Order is already {order['status']} and cannot change", 409)

    conn = db.get_connection()
    try:
        cursor = conn.cursor(dictionary=True)

        if new_status == "cancelled":
            cursor.execute(
                "SELECT * FROM order_items WHERE order_id = %s", (order_id,)
            )
            for item in cursor.fetchall():
                cursor.execute(
                    "UPDATE products SET stock_quantity = stock_quantity + %s WHERE product_id = %s",
                    (item["quantity"], item["product_id"]),
                )
                cursor.execute(
                    """INSERT INTO inventory_transactions
                       (product_id, change_qty, transaction_type, reference_order_id, note)
                       VALUES (%s, %s, 'adjustment', %s, %s)""",
                    (item["product_id"], item["quantity"], order_id, f"Order #{order_id} cancelled - restock"),
                )

        cursor.execute(
            "UPDATE orders SET status = %s WHERE order_id = %s", (new_status, order_id)
        )
        conn.commit()
    except Exception as exc:
        conn.rollback()
        return error_response(f"Could not update order: {exc}", 500)
    finally:
        conn.close()

    return success_response(_order_with_items(order_id))
