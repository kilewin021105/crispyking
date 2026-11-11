"""Costs & Expenses module: operating costs outside of inventory purchasing
(rent, utilities, salaries, supplies, ...). Feeds Reports > Profit & Loss
alongside revenue and products.cost_price (COGS)."""
from flask import Blueprint, request

import db
from utils.validators import (
    error_response,
    is_positive_number,
    require_fields,
    success_response,
)

expenses_bp = Blueprint("expenses", __name__, url_prefix="/api/expenses")

VALID_PAYMENT_METHODS = {"cash", "card", "bank_transfer", "mobile"}

DEFAULT_CATEGORIES = [
    "Rent", "Utilities", "Salaries & Wages", "Supplies & Ingredients",
    "Equipment & Maintenance", "Marketing", "Transport & Delivery",
    "Licenses & Permits", "Other",
]


def _validate_expense_payload(payload, partial=False):
    """Returns an error message, or None if the payload is valid."""
    if not partial:
        missing = require_fields(payload, ["category", "amount", "expense_date"])
        if missing:
            return f"Missing required fields: {', '.join(missing)}"

    if "amount" in payload and not is_positive_number(payload["amount"]):
        return "amount must be a positive number"

    if "payment_method" in payload and payload["payment_method"] not in VALID_PAYMENT_METHODS:
        return f"payment_method must be one of {sorted(VALID_PAYMENT_METHODS)}"

    return None


@expenses_bp.get("")
def list_expenses():
    """GET /api/expenses?category=&start_date=&end_date=&limit=100"""
    category = request.args.get("category")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    limit = min(int(request.args.get("limit", 100)), 500)

    where_sql = " WHERE 1=1"
    params = []
    if category:
        where_sql += " AND e.category = %s"
        params.append(category)
    if start_date:
        where_sql += " AND e.expense_date >= %s"
        params.append(start_date)
    if end_date:
        where_sql += " AND e.expense_date <= %s"
        params.append(end_date)

    # total_amount is a separate aggregate over the FULL filtered set — never
    # just the (LIMIT-capped) rows below, so "Total Expenses" stays correct
    # even once a filtered range holds more entries than one page shows.
    total_row = db.query_one(
        f"SELECT COALESCE(SUM(e.amount), 0) AS total FROM expenses e{where_sql}", params
    )
    total_amount = round(float(total_row["total"]), 2)

    rows = db.query_all(
        f"""SELECT e.*, u.full_name AS recorded_by_name
            FROM expenses e
            LEFT JOIN users u ON u.user_id = e.recorded_by
            {where_sql}
            ORDER BY e.expense_date DESC, e.expense_id DESC LIMIT %s""",
        params + [limit],
    )
    for r in rows:
        r["amount"] = float(r["amount"])
        r["expense_date"] = r["expense_date"].isoformat()
    return success_response(rows, count=len(rows), total_amount=total_amount)


@expenses_bp.get("/categories")
def list_categories():
    """Curated defaults merged with any custom categories already in use —
    keeps the picker useful without locking the schema to an ENUM."""
    rows = db.query_all("SELECT DISTINCT category FROM expenses ORDER BY category")
    used = [r["category"] for r in rows]
    merged = list(DEFAULT_CATEGORIES)
    for cat in used:
        if cat not in merged:
            merged.append(cat)
    return success_response(merged)


@expenses_bp.get("/summary")
def expenses_summary():
    """GET /api/expenses/summary?days=30 — total + breakdown by category."""
    days = int(request.args.get("days", 30))

    total_row = db.query_one(
        """SELECT COUNT(*) AS expense_count, COALESCE(SUM(amount), 0) AS total_expenses
           FROM expenses WHERE expense_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)""",
        (days,),
    )
    total_row["total_expenses"] = float(total_row["total_expenses"])

    by_category = db.query_all(
        """SELECT category, COUNT(*) AS entry_count, SUM(amount) AS total
           FROM expenses
           WHERE expense_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
           GROUP BY category
           ORDER BY total DESC""",
        (days,),
    )
    for r in by_category:
        r["total"] = float(r["total"])

    return success_response({
        "window_days": days,
        "total_expenses": total_row["total_expenses"],
        "expense_count": total_row["expense_count"],
        "by_category": by_category,
    })


def _fetch_expense(expense_id):
    expense = db.query_one("SELECT * FROM expenses WHERE expense_id = %s", (expense_id,))
    if expense:
        expense["amount"] = float(expense["amount"])
        expense["expense_date"] = expense["expense_date"].isoformat()
    return expense


@expenses_bp.get("/<int:expense_id>")
def get_expense(expense_id):
    expense = _fetch_expense(expense_id)
    if not expense:
        return error_response("Expense not found", 404)
    return success_response(expense)


@expenses_bp.post("")
def create_expense():
    """Body: { "category", "amount", "expense_date", "description", "payment_method",
               "recorded_by", "note" }"""
    payload = request.get_json(silent=True) or {}
    err = _validate_expense_payload(payload)
    if err:
        return error_response(err, 422)

    expense_id, _ = db.execute(
        """INSERT INTO expenses
           (category, description, amount, expense_date, payment_method, recorded_by, note)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            payload["category"].strip(),
            payload.get("description"),
            payload["amount"],
            payload["expense_date"],
            payload.get("payment_method", "cash"),
            payload.get("recorded_by"),
            payload.get("note"),
        ),
    )
    return success_response(_fetch_expense(expense_id), 201)


@expenses_bp.put("/<int:expense_id>")
def update_expense(expense_id):
    existing = db.query_one("SELECT * FROM expenses WHERE expense_id = %s", (expense_id,))
    if not existing:
        return error_response("Expense not found", 404)

    payload = request.get_json(silent=True) or {}
    err = _validate_expense_payload(payload, partial=True)
    if err:
        return error_response(err, 422)

    editable_fields = ["category", "description", "amount", "expense_date", "payment_method", "note"]
    updates = {k: v for k, v in payload.items() if k in editable_fields}
    if not updates:
        return error_response("No valid fields to update", 422)

    set_clause = ", ".join(f"{field} = %s" for field in updates)
    params = list(updates.values()) + [expense_id]
    db.execute(f"UPDATE expenses SET {set_clause} WHERE expense_id = %s", params)

    return success_response(_fetch_expense(expense_id))


@expenses_bp.delete("/<int:expense_id>")
def delete_expense(expense_id):
    existing = db.query_one("SELECT * FROM expenses WHERE expense_id = %s", (expense_id,))
    if not existing:
        return error_response("Expense not found", 404)

    db.execute("DELETE FROM expenses WHERE expense_id = %s", (expense_id,))
    return success_response({"expense_id": expense_id, "deleted": True})
