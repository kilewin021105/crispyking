-- =====================================================================
-- Seed data: Crispy King suppliers + menu + ingredients + settings
-- Safe to re-run: uses ON DUPLICATE KEY UPDATE guarded by unique keys
-- =====================================================================

USE crispy_king_db;

-- ---------------------------------------------------------------------
-- Suppliers (3)
-- ---------------------------------------------------------------------
INSERT INTO suppliers (supplier_id, name, contact_person, phone, email, address) VALUES
    (1, 'Golden Poultry Farms',           'Grace Santos',   '+63-917-345-0001', 'sales@goldenpoultry.ph',  'Cebu City, Philippines'),
    (2, 'Crispy Coat Ingredients Co.',    'Juan Bautista',  '+63-917-345-0002', 'orders@crispycoat.ph',    'Cebu City, Philippines'),
    (3, 'Metro Beverage & Packaging Ltd.','Pedro Reyes',    '+63-917-345-0003', 'info@metrobevpack.ph',    'Mandaue City, Philippines')
ON DUPLICATE KEY UPDATE name = VALUES(name), contact_person = VALUES(contact_person),
    phone = VALUES(phone), email = VALUES(email), address = VALUES(address);

-- ---------------------------------------------------------------------
-- Retire the old demo menu (soft-delete only — never hard-delete, in
-- case any of these are still referenced by past orders' order_items).
-- ---------------------------------------------------------------------
UPDATE products SET is_active = 0
WHERE sku IN ('CHK-001','CHK-002','CHK-003','CHK-004','BUR-001','BUR-002',
              'SID-001','SID-002','SID-003','BEV-001','BEV-002','DES-001');

-- ---------------------------------------------------------------------
-- Products (12) — Crispy King menu: fried chicken + Filipino street food
-- ---------------------------------------------------------------------
INSERT INTO products (sku, name, description, category, price, cost_price, supplier_id, stock_quantity, reorder_level) VALUES
    ('CHKW-001', 'Chicken Wings',   'Crispy fried chicken wings',            'Chicken',     50.00, 28.00, 1, 60, 15),
    ('CHKT-001', 'Chicken Thigh',   'Crispy fried chicken thigh',            'Chicken',     50.00, 27.00, 1, 60, 15),
    ('CHKL-001', 'Chicken Leg',     'Crispy fried chicken leg',              'Chicken',     50.00, 26.00, 1, 60, 15),
    ('CHKB-001', 'Chicken Breast',  'Crispy fried chicken breast',           'Chicken',     50.00, 29.00, 1, 50, 15),
    ('SNK-001',  'Meat Balls',      'House-style fried meat balls',          'Street Food', 10.00, 5.00,  2, 100, 25),
    ('SNK-002',  'Lumpia',          'Crispy fried spring rolls',             'Street Food', 8.00,  4.00,  2, 100, 25),
    ('SNK-003',  'Ngohiong',        'Cebu-style five-spice meat roll',       'Street Food', 12.00, 6.00,  2, 80,  20),
    ('SNK-004',  'Siomai',          'Steamed-then-fried pork siomai',        'Street Food', 30.00, 15.00, 2, 80,  20),
    ('BEV-101',  'Mountain Dew',    'Chilled Mountain Dew, bottled',         'Beverages',   25.00, 15.00, 3, 80,  20),
    ('BEV-102',  'Pepsi',           'Chilled Pepsi, bottled',                'Beverages',   20.00, 12.00, 3, 80,  20),
    ('BEV-103',  'Meryenda',        'Chilled Meryenda drink',                'Beverages',   20.00, 12.00, 3, 60,  15),
    ('BEV-104',  'Sting',           'Chilled Sting energy drink, bottled',   'Beverages',   15.00, 9.00,  3, 60,  15)
ON DUPLICATE KEY UPDATE
    name = VALUES(name), description = VALUES(description), category = VALUES(category),
    price = VALUES(price), cost_price = VALUES(cost_price), supplier_id = VALUES(supplier_id),
    stock_quantity = VALUES(stock_quantity), reorder_level = VALUES(reorder_level);

-- ---------------------------------------------------------------------
-- Ingredients (12) — raw materials/supplies needed to make the menu
-- above: oil, breading, wrappers, fuel, packaging, etc.
-- ---------------------------------------------------------------------
INSERT INTO ingredients (name, unit, stock_quantity, reorder_level, cost_per_unit, supplier_id) VALUES
    ('Cooking Oil',               'liters', 40, 10, 2.50,  2),
    ('All-Purpose Flour',         'kg',     25, 8,  1.20,  2),
    ('Crispy Breading Mix',       'kg',     20, 6,  2.80,  2),
    ('Salt & Seasoning Mix',      'kg',     10, 3,  1.50,  2),
    ('Garlic',                    'kg',     5,  2,  3.00,  2),
    ('Ground Pork',               'kg',     15, 5,  6.50,  2),
    ('Soy Sauce',                 'liters', 12, 4,  1.80,  2),
    ('Vinegar',                   'liters', 10, 3,  1.20,  2),
    ('Lumpia Wrappers',           'pack',   20, 5,  3.50,  2),
    ('Siomai Wrappers',           'pack',   15, 5,  3.80,  2),
    ('LPG Gas',                   'tank',   3,  1,  18.00, 3),
    ('Disposable Cups & Bags',    'pack',   30, 8,  4.00,  3)
ON DUPLICATE KEY UPDATE
    unit = VALUES(unit), reorder_level = VALUES(reorder_level),
    cost_per_unit = VALUES(cost_per_unit), supplier_id = VALUES(supplier_id);

-- ---------------------------------------------------------------------
-- Settings (defaults) — editable later from the Settings tab; re-running
-- this file never clobbers a value an admin has already changed, since
-- the UPDATE clause is a no-op (sets a column to its own value).
-- ---------------------------------------------------------------------
INSERT INTO settings (setting_key, setting_value) VALUES
    ('business_name',    'Crispy King'),
    ('currency_symbol',  '₱'),
    ('tax_rate',         '0.10'),
    ('business_phone',   '+63-917-000-0000'),
    ('business_address', 'Cebu City, Philippines'),
    ('receipt_footer',   'Thank you for choosing Crispy King!')
ON DUPLICATE KEY UPDATE setting_key = setting_key;
