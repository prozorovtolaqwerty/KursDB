PRAGMA foreign_keys = ON;

DROP VIEW IF EXISTS v_product_turnover;
DROP VIEW IF EXISTS v_staff;
DROP VIEW IF EXISTS v_products;

DROP TABLE IF EXISTS issue_lines;
DROP TABLE IF EXISTS issues;
DROP TABLE IF EXISTS stock;
DROP TABLE IF EXISTS receipt_lines;
DROP TABLE IF EXISTS receipts;
DROP TABLE IF EXISTS staff;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS warehouses;
DROP TABLE IF EXISTS positions;

CREATE TABLE positions (
    position_id INTEGER PRIMARY KEY,
    title       TEXT    NOT NULL,
    base_salary REAL    NOT NULL DEFAULT 35000,
    CONSTRAINT positions_title_not_empty CHECK (length(trim(title)) > 0),
    CONSTRAINT positions_title_unique UNIQUE (title),
    CONSTRAINT positions_salary_positive CHECK (base_salary > 0)
);

CREATE TABLE warehouses (
    warehouse_no INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    manager      TEXT    NOT NULL,
    address      TEXT    NOT NULL,
    phone        TEXT,
    CONSTRAINT warehouses_no_positive CHECK (warehouse_no > 0),
    CONSTRAINT warehouses_name_not_empty CHECK (length(trim(name)) > 0),
    CONSTRAINT warehouses_name_unique UNIQUE (name),
    CONSTRAINT warehouses_manager_not_empty CHECK (length(trim(manager)) > 0)
);

CREATE TABLE staff (
    warehouse_no INTEGER NOT NULL,
    inn          TEXT    NOT NULL,
    full_name    TEXT    NOT NULL,
    position_id  INTEGER NOT NULL,
    hired_on     TEXT    NOT NULL DEFAULT (date('now')),
    phone        TEXT,
    PRIMARY KEY (warehouse_no, inn),
    CONSTRAINT staff_inn_unique UNIQUE (inn),
    CONSTRAINT staff_inn_digits CHECK (
        length(inn) = 12 AND inn NOT GLOB '*[^0-9]*'
    ),
    CONSTRAINT staff_name_not_empty CHECK (length(trim(full_name)) > 0),
    CONSTRAINT staff_warehouse
        FOREIGN KEY (warehouse_no) REFERENCES warehouses (warehouse_no)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT staff_position
        FOREIGN KEY (position_id) REFERENCES positions (position_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    sku        TEXT    NOT NULL,
    name       TEXT    NOT NULL,
    unit       TEXT    NOT NULL DEFAULT 'шт',
    category   TEXT    NOT NULL DEFAULT 'Прочее',
    CONSTRAINT products_sku_not_empty CHECK (length(trim(sku)) > 0),
    CONSTRAINT products_sku_unique UNIQUE (sku),
    CONSTRAINT products_name_not_empty CHECK (length(trim(name)) > 0),
    CONSTRAINT products_unit_not_empty CHECK (length(trim(unit)) > 0)
);

CREATE TABLE receipts (
    invoice_no   INTEGER PRIMARY KEY,
    warehouse_no INTEGER NOT NULL,
    receipt_date TEXT    NOT NULL DEFAULT (date('now')),
    supplier     TEXT    NOT NULL,
    supplier_doc TEXT,
    CONSTRAINT receipts_no_positive CHECK (invoice_no > 0),
    CONSTRAINT receipts_supplier_not_empty CHECK (length(trim(supplier)) > 0),
    CONSTRAINT receipts_warehouse
        FOREIGN KEY (warehouse_no) REFERENCES warehouses (warehouse_no)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE receipt_lines (
    invoice_no      INTEGER NOT NULL,
    line_no         INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    nomenclature_no TEXT    NOT NULL,
    price           REAL    NOT NULL,
    qty             REAL    NOT NULL,
    PRIMARY KEY (invoice_no, line_no),
    CONSTRAINT receipt_line_nom_unique UNIQUE (nomenclature_no),
    CONSTRAINT receipt_line_no_positive CHECK (line_no > 0),
    CONSTRAINT receipt_line_nom_not_empty CHECK (length(trim(nomenclature_no)) > 0),
    CONSTRAINT receipt_line_price CHECK (price >= 0),
    CONSTRAINT receipt_line_qty CHECK (qty > 0),
    CONSTRAINT receipt_line_header
        FOREIGN KEY (invoice_no) REFERENCES receipts (invoice_no)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT receipt_line_product
        FOREIGN KEY (product_id) REFERENCES products (product_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE issues (
    invoice_no   INTEGER PRIMARY KEY,
    warehouse_no INTEGER NOT NULL,
    issue_date   TEXT    NOT NULL DEFAULT (date('now')),
    customer     TEXT    NOT NULL,
    CONSTRAINT issues_no_positive CHECK (invoice_no > 0),
    CONSTRAINT issues_customer_not_empty CHECK (length(trim(customer)) > 0),
    CONSTRAINT issues_warehouse
        FOREIGN KEY (warehouse_no) REFERENCES warehouses (warehouse_no)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE issue_lines (
    invoice_no      INTEGER NOT NULL,
    line_no         INTEGER NOT NULL,
    nomenclature_no TEXT    NOT NULL,
    sale_price      REAL    NOT NULL,
    qty             REAL    NOT NULL,
    PRIMARY KEY (invoice_no, line_no),
    CONSTRAINT issue_line_no_positive CHECK (line_no > 0),
    CONSTRAINT issue_line_price CHECK (sale_price >= 0),
    CONSTRAINT issue_line_qty CHECK (qty > 0),
    CONSTRAINT issue_line_header
        FOREIGN KEY (invoice_no) REFERENCES issues (invoice_no)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT issue_line_lot
        FOREIGN KEY (nomenclature_no)
        REFERENCES receipt_lines (nomenclature_no)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE stock (
    nomenclature_no TEXT    PRIMARY KEY,
    warehouse_no    INTEGER NOT NULL,
    product_id      INTEGER NOT NULL,
    purchase_price  REAL    NOT NULL,
    qty_in          REAL    NOT NULL,
    qty_out         REAL    NOT NULL DEFAULT 0,
    qty_left        REAL    NOT NULL,
    CONSTRAINT stock_price CHECK (purchase_price >= 0),
    CONSTRAINT stock_consistent CHECK (
        qty_in >= 0
        AND qty_out >= 0
        AND qty_left >= 0
        AND abs(qty_left - (qty_in - qty_out)) < 0.001
    ),
    CONSTRAINT stock_lot
        FOREIGN KEY (nomenclature_no)
        REFERENCES receipt_lines (nomenclature_no)
        ON UPDATE RESTRICT ON DELETE CASCADE,
    CONSTRAINT stock_warehouse
        FOREIGN KEY (warehouse_no) REFERENCES warehouses (warehouse_no)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT stock_product
        FOREIGN KEY (product_id) REFERENCES products (product_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX idx_staff_position ON staff (position_id);
CREATE INDEX idx_staff_name ON staff (full_name);
CREATE INDEX idx_receipts_warehouse_date ON receipts (warehouse_no, receipt_date);
CREATE INDEX idx_receipt_lines_product ON receipt_lines (product_id);
CREATE INDEX idx_issues_warehouse_date ON issues (warehouse_no, issue_date);
CREATE INDEX idx_issue_lines_nom ON issue_lines (nomenclature_no);
CREATE INDEX idx_products_name ON products (name);
CREATE INDEX idx_stock_warehouse_product ON stock (warehouse_no, product_id);

CREATE VIEW v_products AS
SELECT product_id, sku, name, unit, category
FROM products;

CREATE VIEW v_staff AS
SELECT s.inn,
       s.full_name,
       s.hired_on,
       s.phone,
       w.warehouse_no,
       w.name AS warehouse_name,
       p.title AS position_title,
       p.base_salary
FROM staff s
JOIN warehouses w ON w.warehouse_no = s.warehouse_no
JOIN positions p ON p.position_id = s.position_id;

CREATE VIEW v_product_turnover AS
SELECT p.product_id,
       p.name AS product_name,
       ROUND(SUM(l.qty), 3) AS qty_sold,
       ROUND(SUM(l.qty * l.sale_price), 2) AS revenue
FROM issue_lines l
JOIN stock s ON s.nomenclature_no = l.nomenclature_no
JOIN products p ON p.product_id = s.product_id
GROUP BY p.product_id, p.name
HAVING SUM(l.qty) >= 10;

CREATE TRIGGER trg_receipt_line_ai
AFTER INSERT ON receipt_lines
BEGIN
    INSERT INTO stock (
        nomenclature_no, warehouse_no, product_id, purchase_price,
        qty_in, qty_out, qty_left
    )
    SELECT NEW.nomenclature_no,
           r.warehouse_no,
           NEW.product_id,
           NEW.price,
           NEW.qty,
           0,
           NEW.qty
    FROM receipts r
    WHERE r.invoice_no = NEW.invoice_no;
END;

CREATE TRIGGER trg_receipt_line_bu
BEFORE UPDATE ON receipt_lines
BEGIN
    SELECT RAISE(ABORT, 'Номенклатурный номер партии менять нельзя')
    WHERE NEW.nomenclature_no <> OLD.nomenclature_no;

    SELECT RAISE(ABORT, 'Товар партии менять нельзя')
    WHERE NEW.product_id <> OLD.product_id;

    SELECT RAISE(ABORT, 'Количество прихода меньше уже отгруженного')
    WHERE NEW.qty < (
        SELECT qty_out
        FROM stock
        WHERE nomenclature_no = OLD.nomenclature_no
    );
END;

CREATE TRIGGER trg_receipt_line_au
AFTER UPDATE ON receipt_lines
BEGIN
    UPDATE stock
    SET qty_in = NEW.qty,
        purchase_price = NEW.price,
        qty_left = NEW.qty - qty_out
    WHERE nomenclature_no = NEW.nomenclature_no;
END;

CREATE TRIGGER trg_receipt_line_bd
BEFORE DELETE ON receipt_lines
BEGIN
    SELECT RAISE(ABORT, 'Нельзя удалить строку прихода: по партии уже был расход')
    WHERE COALESCE((
        SELECT qty_out
        FROM stock
        WHERE nomenclature_no = OLD.nomenclature_no
    ), 0) > 0;
END;

CREATE TRIGGER trg_receipt_line_ad
AFTER DELETE ON receipt_lines
BEGIN
    DELETE FROM stock
    WHERE nomenclature_no = OLD.nomenclature_no;
END;

CREATE TRIGGER trg_receipt_warehouse_au
AFTER UPDATE OF warehouse_no ON receipts
WHEN NEW.warehouse_no <> OLD.warehouse_no
BEGIN
    SELECT RAISE(ABORT, 'Нельзя перенести накладную на другой склад: по ней уже был расход')
    WHERE EXISTS (SELECT 1 FROM warehouses WHERE warehouse_no = OLD.warehouse_no)
      AND EXISTS (
        SELECT 1
        FROM receipt_lines rl
        JOIN stock s ON s.nomenclature_no = rl.nomenclature_no
        WHERE rl.invoice_no = NEW.invoice_no
          AND s.qty_out > 0
    );

    UPDATE stock
    SET warehouse_no = NEW.warehouse_no
    WHERE nomenclature_no IN (
        SELECT nomenclature_no
        FROM receipt_lines
        WHERE invoice_no = NEW.invoice_no
    );
END;

CREATE TRIGGER trg_warehouse_no_au
AFTER UPDATE OF warehouse_no ON warehouses
WHEN NEW.warehouse_no <> OLD.warehouse_no
BEGIN
    UPDATE stock
    SET warehouse_no = NEW.warehouse_no
    WHERE warehouse_no = OLD.warehouse_no;
END;

CREATE TRIGGER trg_issue_line_bi
BEFORE INSERT ON issue_lines
BEGIN
    SELECT RAISE(ABORT, 'Партия не найдена на остатках')
    WHERE NOT EXISTS (
        SELECT 1 FROM stock WHERE nomenclature_no = NEW.nomenclature_no
    );

    SELECT RAISE(ABORT, 'Партия принадлежит другому складу')
    WHERE (
        SELECT warehouse_no FROM stock WHERE nomenclature_no = NEW.nomenclature_no
    ) <> (
        SELECT warehouse_no FROM issues WHERE invoice_no = NEW.invoice_no
    );

    SELECT RAISE(ABORT, 'Недостаточно товара на остатке')
    WHERE (
        SELECT qty_left FROM stock WHERE nomenclature_no = NEW.nomenclature_no
    ) < NEW.qty;
END;

CREATE TRIGGER trg_issue_line_ai
AFTER INSERT ON issue_lines
BEGIN
    UPDATE stock
    SET qty_out = qty_out + NEW.qty,
        qty_left = qty_in - (qty_out + NEW.qty)
    WHERE nomenclature_no = NEW.nomenclature_no;
END;

CREATE TRIGGER trg_issue_line_bu
BEFORE UPDATE ON issue_lines
BEGIN
    SELECT RAISE(ABORT, 'Нельзя менять номенклатурный номер строки расхода')
    WHERE NEW.nomenclature_no <> OLD.nomenclature_no;

    SELECT RAISE(ABORT, 'Партия принадлежит другому складу')
    WHERE (
        SELECT warehouse_no FROM stock WHERE nomenclature_no = NEW.nomenclature_no
    ) <> (
        SELECT warehouse_no FROM issues WHERE invoice_no = NEW.invoice_no
    );

    SELECT RAISE(ABORT, 'Недостаточно товара на остатке')
    WHERE (
        SELECT qty_left + OLD.qty
        FROM stock
        WHERE nomenclature_no = OLD.nomenclature_no
    ) < NEW.qty;
END;

CREATE TRIGGER trg_issue_line_au
AFTER UPDATE ON issue_lines
BEGIN
    UPDATE stock
    SET qty_out = qty_out - OLD.qty + NEW.qty,
        qty_left = qty_in - (qty_out - OLD.qty + NEW.qty)
    WHERE nomenclature_no = NEW.nomenclature_no;
END;

CREATE TRIGGER trg_issue_line_ad
AFTER DELETE ON issue_lines
BEGIN
    UPDATE stock
    SET qty_out = qty_out - OLD.qty,
        qty_left = qty_in - (qty_out - OLD.qty)
    WHERE nomenclature_no = OLD.nomenclature_no;
END;
