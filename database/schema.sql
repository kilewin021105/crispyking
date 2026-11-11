-- =====================================================================
-- Crispy King — POS / Ordering System — Database Schema
-- Matches architecture: Menu | Orders | Inventory | Reports -> Database
-- =====================================================================

CREATE DATABASE IF NOT EXISTS crispy_king_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE crispy_king_db;

-- ---------------------------------------------------------------------
-- Suppliers  (feed the Menu/Inventory modules)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id     INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    contact_person  VARCHAR(150),
    phone           VARCHAR(30),
    email           VARCHAR(150),
    address         VARCHAR(255),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Users  (Cashier / Admin accounts operating the Web application)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id         INT AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(50) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    full_name       VARCHAR(150) NOT NULL,
    role            ENUM('cashier', 'admin') NOT NULL DEFAULT 'cashier',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Products  (Menu module: item, prices)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS products (
    product_id      INT AUTO_INCREMENT PRIMARY KEY,
    sku             VARCHAR(50) UNIQUE,
    name            VARCHAR(150) NOT NULL,
    description     TEXT,
    category        VARCHAR(80) NOT NULL DEFAULT 'General',
    price           DECIMAL(10,2) NOT NULL,
    cost_price      DECIMAL(10,2) NOT NULL DEFAULT 0,
    supplier_id     INT,
    stock_quantity  INT NOT NULL DEFAULT 0,
    reorder_level   INT NOT NULL DEFAULT 10,
    is_active       TINYINT(1) NOT NULL DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_products_supplier
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
        ON DELETE SET NULL,
    CONSTRAINT chk_price_positive CHECK (price >= 0),
    INDEX idx_products_category (category),
    INDEX idx_products_active (is_active)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Orders  (Orders module: dine-in / takeout)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    order_id        INT AUTO_INCREMENT PRIMARY KEY,
    order_type      ENUM('dine-in', 'takeout') NOT NULL,
    status          ENUM('pending', 'preparing', 'ready', 'completed', 'cancelled')
                        NOT NULL DEFAULT 'pending',
    customer_name   VARCHAR(150),
    table_number    VARCHAR(10),
    cashier_id      INT,
    payment_method  ENUM('cash', 'card', 'mobile') DEFAULT 'cash',
    subtotal        DECIMAL(10,2) NOT NULL DEFAULT 0,
    tax_amount      DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount    DECIMAL(10,2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_orders_cashier
        FOREIGN KEY (cashier_id) REFERENCES users(user_id)
        ON DELETE SET NULL,
    INDEX idx_orders_status (status),
    INDEX idx_orders_created (created_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Order items  (line items per order)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id   INT AUTO_INCREMENT PRIMARY KEY,
    order_id        INT NOT NULL,
    product_id      INT NOT NULL,
    quantity        INT NOT NULL,
    unit_price      DECIMAL(10,2) NOT NULL,
    line_total      DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_items_order
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_items_product
        FOREIGN KEY (product_id) REFERENCES products(product_id)
        ON DELETE RESTRICT,
    CONSTRAINT chk_qty_positive CHECK (quantity > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Inventory transactions  (Inventory module: stock tracking history)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inventory_transactions (
    transaction_id      INT AUTO_INCREMENT PRIMARY KEY,
    product_id          INT NOT NULL,
    change_qty          INT NOT NULL,          -- positive = restock, negative = sale/waste
    transaction_type     ENUM('restock', 'sale', 'adjustment', 'waste') NOT NULL,
    reference_order_id   INT,
    note                VARCHAR(255),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_inv_product
        FOREIGN KEY (product_id) REFERENCES products(product_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_inv_order
        FOREIGN KEY (reference_order_id) REFERENCES orders(order_id)
        ON DELETE SET NULL,
    INDEX idx_inv_product (product_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Settings  (key/value store: business info, currency, tax rate — lets
-- the system be reconfigured from the Settings tab with no code change
-- or restart, instead of being baked into .env)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS settings (
    setting_key     VARCHAR(50) PRIMARY KEY,
    setting_value   VARCHAR(255) NOT NULL,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Expenses  (Costs & Expenses module: operating costs outside of
-- inventory purchasing — rent, utilities, salaries, etc. Feeds the
-- Reports > Profit & Loss view alongside revenue and cost_price/COGS.)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS expenses (
    expense_id      INT AUTO_INCREMENT PRIMARY KEY,
    category        VARCHAR(80) NOT NULL,
    description     VARCHAR(255),
    amount          DECIMAL(10,2) NOT NULL,
    expense_date    DATE NOT NULL,
    payment_method  ENUM('cash', 'card', 'bank_transfer', 'mobile') NOT NULL DEFAULT 'cash',
    recorded_by     INT,
    note            VARCHAR(255),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_expenses_user
        FOREIGN KEY (recorded_by) REFERENCES users(user_id)
        ON DELETE SET NULL,
    CONSTRAINT chk_expense_amount_positive CHECK (amount > 0),
    INDEX idx_expenses_date (expense_date),
    INDEX idx_expenses_category (category)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Ingredients  (raw materials/supplies used to MAKE the menu — oil,
-- flour, wrappers, gas, packaging, etc. Separate from `products`, which
-- is the sellable finished menu: ingredients aren't sold directly, are
-- tracked in kitchen units (kg/liters/pack) rather than "pieces", and
-- have no customer-facing price.)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingredients (
    ingredient_id   INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL UNIQUE,
    unit            VARCHAR(20) NOT NULL DEFAULT 'pcs',   -- kg, liters, pack, tank, pcs...
    stock_quantity  DECIMAL(10,2) NOT NULL DEFAULT 0,
    reorder_level   DECIMAL(10,2) NOT NULL DEFAULT 0,
    cost_per_unit   DECIMAL(10,2) NOT NULL DEFAULT 0,
    supplier_id     INT,
    is_active       TINYINT(1) NOT NULL DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ingredients_supplier
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
        ON DELETE SET NULL,
    CONSTRAINT chk_ingredient_stock_non_negative CHECK (stock_quantity >= 0),
    INDEX idx_ingredients_active (is_active)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Ingredient transactions  (restock / usage / adjustment / waste audit
-- trail — mirrors inventory_transactions for the finished-goods side)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingredient_transactions (
    transaction_id      INT AUTO_INCREMENT PRIMARY KEY,
    ingredient_id        INT NOT NULL,
    change_qty           DECIMAL(10,2) NOT NULL,   -- positive = restock, negative = usage/waste
    transaction_type     ENUM('restock', 'usage', 'adjustment', 'waste') NOT NULL,
    note                 VARCHAR(255),
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ingtxn_ingredient
        FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id)
        ON DELETE CASCADE,
    INDEX idx_ingtxn_ingredient (ingredient_id)
) ENGINE=InnoDB;
