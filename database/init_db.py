"""
Initializes the pos_system MySQL database:
  1. Runs schema.sql   -> creates database + tables
  2. Runs seed.sql     -> suppliers, menu products, ingredients, default settings
  3. Creates default admin/cashier user accounts (hashed passwords)
  4. Seeds sample expenses (Python-side, since expenses have no natural unique key)

Run from the project root or from database/:
    python database/init_db.py
"""
import os
import sys

import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "crispy_king_db")


def run_sql_file(cursor, path):
    with open(path, "r", encoding="utf-8") as f:
        sql_text = f.read()
    # mysql-connector supports executing multiple ';'-separated statements
    for result in cursor.execute(sql_text, multi=True):
        pass


def seed_users(cursor):
    """Create default admin + cashier accounts if they don't already exist."""
    users = [
        (
            os.getenv("DEFAULT_ADMIN_USERNAME", "admin"),
            os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123"),
            "System Administrator",
            "admin",
        ),
        (
            os.getenv("DEFAULT_CASHIER_USERNAME", "cashier1"),
            os.getenv("DEFAULT_CASHIER_PASSWORD", "cashier123"),
            "Front Counter Cashier",
            "cashier",
        ),
    ]
    for username, password, full_name, role in users:
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            print(f"  - user '{username}' already exists, skipping")
            continue
        cursor.execute(
            """INSERT INTO users (username, password_hash, full_name, role)
               VALUES (%s, %s, %s, %s)""",
            (username, generate_password_hash(password), full_name, role),
        )
        print(f"  - created user '{username}' (role={role}, password={password})")


def seed_expenses(cursor):
    """Seed a few sample operating expenses so Reports/Expenses aren't empty
    on first run. Guarded by a row-count check (not ON DUPLICATE KEY, since
    expenses have no natural unique key) so re-running init_db.py is safe."""
    cursor.execute("SELECT COUNT(*) FROM expenses")
    if cursor.fetchone()[0] > 0:
        print("  - expenses already seeded, skipping")
        return

    admin_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    cursor.execute("SELECT user_id FROM users WHERE username = %s", (admin_username,))
    row = cursor.fetchone()
    recorded_by = row[0] if row else None

    # (days_ago, category, description, amount, payment_method)
    sample_expenses = [
        (28, "Rent",                    "Monthly shop rent",                    450.00, "bank_transfer"),
        (25, "Utilities",                "Electricity bill",                     86.50,  "card"),
        (25, "Utilities",                "Water bill",                           22.00,  "cash"),
        (21, "Salaries & Wages",         "Weekly staff wages",                   310.00, "bank_transfer"),
        (18, "Supplies & Ingredients",   "Cooking oil restock",                  64.20,  "cash"),
        (14, "Salaries & Wages",         "Weekly staff wages",                   310.00, "bank_transfer"),
        (10, "Marketing",                "Social media ad boost",                40.00,  "card"),
        (7,  "Equipment & Maintenance",  "Fryer servicing",                      95.00,  "cash"),
        (7,  "Salaries & Wages",         "Weekly staff wages",                   310.00, "bank_transfer"),
        (3,  "Transport & Delivery",     "Fuel for delivery run",                28.75,  "cash"),
        (1,  "Licenses & Permits",       "Health inspection fee",                50.00,  "bank_transfer"),
    ]
    for days_ago, category, description, amount, payment_method in sample_expenses:
        cursor.execute(
            """INSERT INTO expenses
               (category, description, amount, expense_date, payment_method, recorded_by, note)
               VALUES (%s, %s, %s, DATE_SUB(CURDATE(), INTERVAL %s DAY), %s, %s, 'Seed data')""",
            (category, description, amount, days_ago, payment_method, recorded_by),
        )
    print(f"  - seeded {len(sample_expenses)} sample expenses")


def main():
    print(f"Connecting to MySQL at {DB_HOST}:{DB_PORT} as {DB_USER} ...")
    conn = mysql.connector.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD
    )
    cursor = conn.cursor()

    print("Running schema.sql (create database + tables) ...")
    run_sql_file(cursor, os.path.join(BASE_DIR, "schema.sql"))
    conn.commit()

    print("Running seed.sql (suppliers + products) ...")
    cursor.execute(f"USE {DB_NAME}")
    run_sql_file(cursor, os.path.join(BASE_DIR, "seed.sql"))
    conn.commit()

    print("Seeding default users ...")
    cursor.execute(f"USE {DB_NAME}")
    seed_users(cursor)
    conn.commit()

    print("Seeding sample expenses ...")
    cursor.execute(f"USE {DB_NAME}")
    seed_expenses(cursor)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM suppliers")
    supplier_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
    product_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM ingredients WHERE is_active = 1")
    ingredient_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM settings")
    settings_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM expenses")
    expense_count = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    print("\nDatabase ready:")
    print(f"  suppliers  : {supplier_count}")
    print(f"  products   : {product_count} (active)")
    print(f"  ingredients: {ingredient_count} (active)")
    print(f"  users      : {user_count}")
    print(f"  settings   : {settings_count}")
    print(f"  expenses   : {expense_count}")


if __name__ == "__main__":
    try:
        main()
    except mysql.connector.Error as err:
        print(f"MySQL error: {err}", file=sys.stderr)
        sys.exit(1)
