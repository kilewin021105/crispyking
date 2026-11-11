"""Reports module: sales & analytics aggregated from orders/order_items."""
from flask import Blueprint, request

import db
from utils.validators import success_response

reports_bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@reports_bp.get("/summary")
def sales_summary():
    """GET /api/reports/summary?days=30 — headline KPIs for a trailing window."""
    days = int(request.args.get("days", 30))

    summary = db.query_one(
        """SELECT
             COUNT(*) AS order_count,
             COALESCE(SUM(total_amount), 0) AS total_revenue,
             COALESCE(AVG(total_amount), 0) AS avg_order_value
           FROM orders
           WHERE status = 'completed'
             AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)""",
        (days,),
    )
    summary["total_revenue"] = float(summary["total_revenue"])
    summary["avg_order_value"] = round(float(summary["avg_order_value"]), 2)

    by_status = db.query_all(
        "SELECT status, COUNT(*) AS count FROM orders GROUP BY status"
    )

    return success_response({"window_days": days, "summary": summary, "orders_by_status": by_status})


@reports_bp.get("/top-products")
def top_products():
    """GET /api/reports/top-products?limit=5&days=30"""
    limit = min(int(request.args.get("limit", 5)), 50)
    days = int(request.args.get("days", 30))

    rows = db.query_all(
        """SELECT p.product_id, p.name, p.category,
                  SUM(oi.quantity) AS units_sold,
                  SUM(oi.line_total) AS revenue
           FROM order_items oi
           JOIN products p ON p.product_id = oi.product_id
           JOIN orders o ON o.order_id = oi.order_id
           WHERE o.status = 'completed'
             AND o.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
           GROUP BY p.product_id, p.name, p.category
           ORDER BY units_sold DESC
           LIMIT %s""",
        (days, limit),
    )
    for r in rows:
        r["revenue"] = float(r["revenue"])
    return success_response(rows, count=len(rows))


@reports_bp.get("/sales-by-category")
def sales_by_category():
    days = int(request.args.get("days", 30))
    rows = db.query_all(
        """SELECT p.category,
                  SUM(oi.quantity) AS units_sold,
                  SUM(oi.line_total) AS revenue
           FROM order_items oi
           JOIN products p ON p.product_id = oi.product_id
           JOIN orders o ON o.order_id = oi.order_id
           WHERE o.status = 'completed'
             AND o.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
           GROUP BY p.category
           ORDER BY revenue DESC""",
        (days,),
    )
    for r in rows:
        r["revenue"] = float(r["revenue"])
    return success_response(rows, count=len(rows))


@reports_bp.get("/daily-sales")
def daily_sales():
    """GET /api/reports/daily-sales?days=7 — for a trend chart."""
    days = min(int(request.args.get("days", 7)), 90)
    rows = db.query_all(
        """SELECT DATE(created_at) AS day,
                  COUNT(*) AS order_count,
                  COALESCE(SUM(total_amount), 0) AS revenue
           FROM orders
           WHERE status = 'completed'
             AND created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
           GROUP BY DATE(created_at)
           ORDER BY day""",
        (days,),
    )
    for r in rows:
        r["day"] = r["day"].isoformat()
        r["revenue"] = float(r["revenue"])
    return success_response(rows, count=len(rows))


@reports_bp.get("/profit-loss")
def profit_loss():
    """GET /api/reports/profit-loss?days=30 — the "cost and expenses" view:
    Revenue - COGS = Gross Profit; Gross Profit - Operating Expenses = Net Profit."""
    days = int(request.args.get("days", 30))

    revenue_row = db.query_one(
        """SELECT COALESCE(SUM(total_amount), 0) AS revenue,
                  COALESCE(SUM(subtotal), 0) AS revenue_ex_tax,
                  COALESCE(SUM(tax_amount), 0) AS tax_collected
           FROM orders
           WHERE status = 'completed'
             AND created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)""",
        (days,),
    )
    cogs_row = db.query_one(
        """SELECT COALESCE(SUM(oi.quantity * p.cost_price), 0) AS cogs
           FROM order_items oi
           JOIN orders o ON o.order_id = oi.order_id
           JOIN products p ON p.product_id = oi.product_id
           WHERE o.status = 'completed'
             AND o.created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)""",
        (days,),
    )
    expenses_row = db.query_one(
        """SELECT COALESCE(SUM(amount), 0) AS total_expenses
           FROM expenses
           WHERE expense_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)""",
        (days,),
    )
    expenses_by_category = db.query_all(
        """SELECT category, SUM(amount) AS total
           FROM expenses
           WHERE expense_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
           GROUP BY category
           ORDER BY total DESC""",
        (days,),
    )

    revenue = float(revenue_row["revenue"])
    cogs = float(cogs_row["cogs"])
    total_expenses = float(expenses_row["total_expenses"])
    gross_profit = round(revenue - cogs, 2)
    net_profit = round(gross_profit - total_expenses, 2)

    for r in expenses_by_category:
        r["total"] = float(r["total"])

    return success_response({
        "window_days": days,
        "revenue": round(revenue, 2),
        "cogs": round(cogs, 2),
        "gross_profit": gross_profit,
        "total_expenses": round(total_expenses, 2),
        "net_profit": net_profit,
        "expenses_by_category": expenses_by_category,
    })


@reports_bp.get("/inventory-value")
def inventory_value():
    """Current stock valuation — units on hand x cost price, per product."""
    rows = db.query_all(
        """SELECT product_id, name, category, stock_quantity, cost_price,
                  (stock_quantity * cost_price) AS stock_value
           FROM products
           WHERE is_active = 1
           ORDER BY stock_value DESC"""
    )
    total = 0.0
    for r in rows:
        r["cost_price"] = float(r["cost_price"])
        r["stock_value"] = float(r["stock_value"])
        total += r["stock_value"]
    return success_response({"products": rows, "total_stock_value": round(total, 2)})
