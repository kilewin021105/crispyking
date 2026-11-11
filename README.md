# 🍗 Crispy King — POS / Ordering System

A full-stack restaurant Point-of-Sale & ordering system, built to match this architecture:

```
Customer ─┐                                  ┌─ Menu (items, prices)
          ├──▶  Web application  ─────────────┼─ Orders (dine-in, takeout)
Cashier ──┘      (POS / ordering system)      ├─ Inventory + Ingredients (stock)
Admin   ──┘                                   ├─ Costs & Expenses (P&L)
                                               ├─ Reports (sales, analytics)
                                               └─ Settings (business, currency, tax)
                                                        │
                                                    Database (MySQL)
```

**Stack:** HTML/CSS/JavaScript + Bootstrap 5 + Chart.js (frontend) · Python + Flask (backend) · MySQL (database) · REST API returning JSON.

**Two entry points, no overlap:**
- **`index.html`** — the customer menu. Browsing/ordering only; no login, and no link to the staff side.
- **`pos.html`** — staff & admin only. Reachable by URL, not linked from the customer page. Logs in as `cashier` or `admin`; a handful of tabs (Expenses, Settings, and the cost/margin parts of Reports) only show for `admin`.

---

## Project structure

```
python tutorial/
├── .env                    # local DB/app config (gitignored, holds your MySQL password)
├── .env.example             # template for .env
├── database/
│   ├── schema.sql            # CREATE DATABASE + all tables
│   ├── seed.sql               # suppliers + menu + ingredients + default settings
│   └── init_db.py             # runs schema.sql + seed.sql, creates default admin/cashier users
│                               #   + sample expenses. Idempotent — safe to rerun.
├── backend/
│   ├── app.py                  # Flask app factory, blueprint registration, static serving, error handlers
│   ├── config.py               # loads .env into a Config object (DB creds, bootstrap defaults)
│   ├── db.py                   # MySQL connection pool + query_all/query_one/execute helpers
│   ├── requirements.txt
│   ├── routes/
│   │   ├── menu_routes.py       # GET/POST/PUT/DELETE /api/menu          (Menu module)
│   │   ├── orders_routes.py     # GET/POST /api/orders                   (Orders module)
│   │   ├── inventory_routes.py  # GET/POST /api/inventory                (finished menu items)
│   │   ├── ingredients_routes.py# GET/POST /api/ingredients              (raw materials: oil, wrappers, gas...)
│   │   ├── expenses_routes.py   # GET/POST/PUT/DELETE /api/expenses      (Costs & Expenses module)
│   │   ├── reports_routes.py    # GET /api/reports/*                     (sales + Profit & Loss)
│   │   ├── settings_routes.py   # GET/PUT /api/settings                  (business name, currency, tax rate)
│   │   ├── suppliers_routes.py  # GET/POST/PUT/DELETE /api/suppliers
│   │   └── auth_routes.py       # POST /api/auth/login                   (cashier/admin login)
│   └── utils/
│       ├── validators.py        # request validation + standard JSON response envelopes
│       └── settings.py          # settings table helpers (get_tax_rate(), get_all_settings(), ...)
└── frontend/
    ├── index.html              # Customer-facing menu & ordering page — no login
    ├── pos.html                 # Staff/Admin login + dashboard: Orders / Inventory / Ingredients /
    │                             #   Suppliers / Expenses(admin) / Reports / Settings(admin)
    ├── css/style.css
    └── js/
        ├── api.js                # fetch() wrapper + toast/money helpers + site settings (currency/branding)
        ├── menu.js                # customer menu rendering, cart, order placement
        └── pos.js                 # staff login, role-gated tabs, orders/inventory/ingredients/expenses/
                                    #   reports (incl. Chart.js)/settings/suppliers
```

The Flask app serves **both** the REST API (`/api/*`) and the static frontend from a single process on one port, so there's no CORS to worry about in normal use.

---

## Database schema

| Table | Purpose |
|---|---|
| `suppliers` | Suppliers feeding the menu/inventory/ingredients |
| `products` | **Sellable** menu items — price, cost, stock_quantity, reorder_level, supplier link |
| `ingredients` | **Raw materials** used to make the menu (oil, flour, wrappers, gas, packaging...) — separate from `products` since they aren't sold directly and are tracked in kitchen units (kg/liters/pack) |
| `ingredient_transactions` | Audit trail for ingredient restock/usage/adjustment/waste |
| `users` | Cashier/admin accounts (password hashed with Werkzeug) |
| `orders` | One row per dine-in/takeout order, with computed subtotal/tax/total |
| `order_items` | Line items per order |
| `inventory_transactions` | Full audit trail of every finished-product stock movement (sale, restock, adjustment, waste) |
| `expenses` | Operating costs outside inventory purchasing — rent, utilities, salaries, etc. Feeds Reports > Profit & Loss |
| `settings` | Key/value store — business name, currency symbol, tax rate, receipt info. Editable live from the Settings tab, no restart needed |

Foreign keys enforce referential integrity (e.g. deleting a supplier just nulls the product's `supplier_id`; order items cascade with their order). All tables use `CREATE TABLE IF NOT EXISTS` with indexes declared inline, so `init_db.py` is safe to rerun against an already-initialized database.

---

## Setup & run

### 1. Prerequisites
- Python 3.10+
- MySQL Server running (this project's local instance is on `127.0.0.1:3307` — see `.env`)

### 2. Configure
`.env` at the project root already has your local DB credentials:
```
DB_HOST=127.0.0.1
DB_PORT=3307
DB_USER=root
DB_PASSWORD=********
DB_NAME=crispy_king_db
```

### 3. Install backend dependencies
```powershell
pip install -r backend/requirements.txt
```

### 4. Create & seed the database
```powershell
python database/init_db.py
```
This creates `crispy_king_db`, all tables, suppliers, the menu, ingredients, default settings, sample expenses, and two demo accounts:
- **admin / admin123** — sees every tab, including Expenses and Settings
- **cashier1 / cashier123** — sees Orders / Inventory / Ingredients / Suppliers / Reports (no cost or margin figures)

Re-running `init_db.py` is safe — it won't duplicate suppliers/products/ingredients/users, and it never overwrites a setting you've already changed from the Settings tab.

### 5. Run the backend
```powershell
python backend/app.py
```
Then open:
- **http://127.0.0.1:5000/** — customer ordering page (no login)
- **http://127.0.0.1:5000/pos.html** — staff/admin login (bookmark this — nothing on the customer page links to it)

---

## Costs & Expenses (Profit & Loss)

The **Expenses** tab (admin only) logs operating costs — rent, utilities, salaries, supplies, anything not already captured by inventory purchasing — against a free-form category (a curated list is offered, but typing a new one is always allowed). It always shows a **Total Expenses** figure for whatever date range/category is filtered, plus a top-category breakdown.

The **Reports** tab's Profit & Loss section ties it all together for the selected window:

```
Revenue  −  COGS (Σ quantity × product cost_price on completed orders)  =  Gross Profit
Gross Profit  −  Total Expenses  =  Net Profit (or Net Loss, called out in red)
```

---

## Flexibility — Settings & Ingredients

- **Settings tab** (admin only): business name, currency symbol, tax rate, phone/address, receipt footer. Saving takes effect immediately across both the customer page and the POS — order totals are computed server-side from the live tax rate (`utils/settings.get_tax_rate()`), not a hardcoded constant.
- **Ingredients tab**: everything needed to make the menu (oil, flour, wrappers, gas, packaging...) is trackable with stock/reorder levels and restock history — and isn't a fixed list, since "Add New Ingredient" is always available.

---

## REST API reference

All responses are JSON: `{ "success": true, "data": ... }` or `{ "success": false, "error": "..." }`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/menu?category=&search=` | List menu items |
| GET | `/api/menu/<id>` | Get one product |
| POST/PUT/DELETE | `/api/menu[/<id>]` | Manage products |
| GET | `/api/suppliers` | List suppliers |
| POST/PUT/DELETE | `/api/suppliers[/<id>]` | Manage suppliers |
| GET | `/api/orders?status=&order_type=` | List orders (includes `item_count` per order) |
| GET | `/api/orders/<id>` | Order detail with line items |
| POST | `/api/orders` | Place an order — validates stock, computes totals server-side from the live tax rate, decrements inventory atomically |
| PUT | `/api/orders/<id>/status` | Advance/cancel an order (cancelling restocks items) |
| GET | `/api/inventory` | Finished-menu stock levels, flags low-stock items |
| GET | `/api/inventory/low-stock` | Only items at/under reorder level |
| GET | `/api/inventory/<id>/history` | Stock movement history for a product |
| POST | `/api/inventory/restock` \| `/adjust` | Add stock / manual adjustment |
| GET | `/api/ingredients?search=` | Raw-materials stock levels, flags low-stock |
| GET | `/api/ingredients/low-stock` \| `/value` \| `/<id>/history` | Low-stock list / valuation / audit trail |
| POST | `/api/ingredients` | Add a new ingredient (free-form — "and etc" is always supported) |
| PUT/DELETE | `/api/ingredients/<id>` | Edit / soft-delete an ingredient |
| POST | `/api/ingredients/restock` \| `/adjust` | Add stock / usage-waste-correction adjustment |
| GET | `/api/expenses?category=&start_date=&end_date=` | List expenses (returns `total_amount` for the filtered set) |
| GET | `/api/expenses/categories` | Curated + in-use categories |
| GET | `/api/expenses/summary?days=30` | Total expenses + breakdown by category |
| POST/PUT/DELETE | `/api/expenses[/<id>]` | Log / edit / delete an expense |
| GET | `/api/reports/summary?days=30` | Order count, revenue, avg order value |
| GET | `/api/reports/top-products?limit=5&days=30` | Best sellers |
| GET | `/api/reports/sales-by-category?days=30` | Revenue by category |
| GET | `/api/reports/daily-sales?days=7` | Daily revenue trend (drives the Reports line chart) |
| GET | `/api/reports/inventory-value` | Current finished-goods stock valuation |
| GET | `/api/reports/profit-loss?days=30` | Revenue, COGS, gross profit, **total expenses**, net profit, expenses-by-category |
| GET/PUT | `/api/settings` | Read/update business name, currency, tax rate, receipt info |
| POST | `/api/auth/login` | Cashier/admin login |

### Business logic enforced server-side
- Order totals (subtotal/tax/total) are **always recomputed from current product prices and the live tax-rate setting** — the client cannot spoof totals.
- Placing an order locks the relevant product rows, checks stock, decrements it, and logs an `inventory_transactions` row — all inside one DB transaction (rolls back entirely on any failure).
- Orders can't skip states arbitrarily from the API's perspective; completed/cancelled orders are terminal.
- Cancelling a pending/preparing order automatically restocks its items.
- Like every other route in this API, `/api/expenses` and `/api/settings` have **no server-side auth check** — that's an existing, project-wide gap (there's no session/token layer at all yet), not something specific to the new modules. The POS frontend hides admin-only tabs client-side; a real deployment would need a proper auth layer before treating any of this as access-controlled.
#   c r i s p y k i n g  
 #   c r i s p y k i n g  
 #   C r i s p y k i n g 2 . 0  
 #   p r o j e c t _ n i _ m a a m _ c h o n a  
 #   c r i s p y k i n g  
 #   C r i s p y k i n g 2 . 0  
 