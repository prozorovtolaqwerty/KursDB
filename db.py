import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"
SEED_PATH = BASE_DIR / "seed.sql"
DB_PATH = BASE_DIR / "data" / "warehouse.db"

CONSTRAINT_MESSAGES = {
    "staff_inn_digits": "ИНН должен состоять из 12 цифр.",
    "staff_name_not_empty": "Укажите ФИО сотрудника.",
    "staff_inn_unique": "Сотрудник с таким ИНН уже есть.",
    "positions_salary_positive": "Оклад должен быть больше нуля.",
    "positions_title_unique": "Должность с таким названием уже есть.",
    "positions_title_not_empty": "Укажите название должности.",
    "warehouses_name_unique": "Склад с таким названием уже есть.",
    "warehouses_name_not_empty": "Укажите название склада.",
    "warehouses_manager_not_empty": "Укажите заведующего.",
    "warehouses_no_positive": "Номер склада должен быть больше нуля.",
    "products_sku_unique": "Товар с таким артикулом уже есть.",
    "products_sku_not_empty": "Укажите артикул.",
    "products_name_not_empty": "Укажите наименование товара.",
    "products_unit_not_empty": "Укажите единицу измерения.",
    "receipts_supplier_not_empty": "Укажите поставщика.",
    "issues_customer_not_empty": "Укажите покупателя.",
    "receipt_line_price": "Цена прихода не может быть отрицательной.",
    "receipt_line_qty": "Количество прихода должно быть больше нуля.",
    "issue_line_price": "Цена продажи не может быть отрицательной.",
    "issue_line_qty": "Количество расхода должно быть больше нуля.",
    "receipt_line_nom_unique": "Такой номенклатурный номер уже используется.",
    "stock_consistent": "Остаток партии расходится с приходом и расходом.",
}


def humanize(error):
    text = str(error)
    for key, message in CONSTRAINT_MESSAGES.items():
        if key in text:
            return message
    if "FOREIGN KEY constraint failed" in text:
        return (
            "Операция нарушает связь между таблицами. "
            "Проверьте коды или сначала уберите зависимые записи."
        )
    if "UNIQUE constraint failed" in text:
        return "Такое уникальное значение уже есть. " + text
    if "NOT NULL constraint failed" in text:
        return "Не заполнено обязательное поле. " + text
    return text


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path=None, force=False):
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        conn = connect(path)
        try:
            ready = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'warehouses'"
            ).fetchone()
        finally:
            conn.close()
        if ready:
            return path
    if path.exists():
        path.unlink()
    conn = connect(path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.executescript(SEED_PATH.read_text(encoding="utf-8"))
    finally:
        conn.close()
    return path


def _col(name, label, kind="text", required=False, auto=False, fk=None):
    column = {
        "name": name,
        "label": label,
        "kind": kind,
        "required": required,
        "auto": auto,
    }
    if fk:
        column["fk"] = fk
    return column


def _fk(table, value, label):
    return {"table": table, "value": value, "label": label}


TABLES = [
    {
        "slug": "positions",
        "table": "positions",
        "title": "Должности",
        "group": "Справочники",
        "pk": ["position_id"],
        "columns": [
            _col("position_id", "Код", "int", auto=True),
            _col("title", "Наименование", required=True),
            _col("base_salary", "Оклад", "real", required=True),
        ],
    },
    {
        "slug": "warehouses",
        "table": "warehouses",
        "title": "Склады",
        "group": "Справочники",
        "pk": ["warehouse_no"],
        "columns": [
            _col("warehouse_no", "Номер", "int", required=True),
            _col("name", "Наименование", required=True),
            _col("manager", "Заведующий", required=True),
            _col("address", "Адрес", required=True),
            _col("phone", "Телефон"),
        ],
    },
    {
        "slug": "staff",
        "table": "staff",
        "title": "Персонал",
        "group": "Справочники",
        "pk": ["warehouse_no", "inn"],
        "columns": [
            _col("warehouse_no", "Склад", "int", required=True, fk=_fk("warehouses", "warehouse_no", "name")),
            _col("inn", "ИНН", required=True),
            _col("full_name", "ФИО", required=True),
            _col("position_id", "Должность", "int", required=True, fk=_fk("positions", "position_id", "title")),
            _col("hired_on", "Дата приёма", "date", required=True),
            _col("phone", "Телефон"),
        ],
    },
    {
        "slug": "products",
        "table": "products",
        "title": "Товары",
        "group": "Справочники",
        "pk": ["product_id"],
        "columns": [
            _col("product_id", "Код", "int", auto=True),
            _col("sku", "Артикул", required=True),
            _col("name", "Наименование", required=True),
            _col("unit", "Единица", required=True),
            _col("category", "Категория", required=True),
        ],
    },
    {
        "slug": "receipts",
        "table": "receipts",
        "title": "Приход (шапки)",
        "group": "Документы",
        "pk": ["invoice_no"],
        "columns": [
            _col("invoice_no", "Накладная", "int", required=True),
            _col("warehouse_no", "Склад", "int", required=True, fk=_fk("warehouses", "warehouse_no", "name")),
            _col("receipt_date", "Дата", "date", required=True),
            _col("supplier", "Поставщик", required=True),
            _col("supplier_doc", "Документ поставщика"),
        ],
    },
    {
        "slug": "receipt-lines",
        "table": "receipt_lines",
        "title": "Строки прихода",
        "group": "Документы",
        "pk": ["invoice_no", "line_no"],
        "columns": [
            _col("invoice_no", "Накладная", "int", required=True, fk=_fk("receipts", "invoice_no", "supplier")),
            _col("line_no", "Строка", "int", required=True),
            _col("product_id", "Товар", "int", required=True, fk=_fk("products", "product_id", "name")),
            _col("nomenclature_no", "Номенклатурный номер", required=True),
            _col("price", "Цена", "real", required=True),
            _col("qty", "Количество", "real", required=True),
        ],
    },
    {
        "slug": "issues",
        "table": "issues",
        "title": "Расход (шапки)",
        "group": "Документы",
        "pk": ["invoice_no"],
        "columns": [
            _col("invoice_no", "Накладная", "int", required=True),
            _col("warehouse_no", "Склад", "int", required=True, fk=_fk("warehouses", "warehouse_no", "name")),
            _col("issue_date", "Дата", "date", required=True),
            _col("customer", "Покупатель", required=True),
        ],
    },
    {
        "slug": "issue-lines",
        "table": "issue_lines",
        "title": "Строки расхода",
        "group": "Документы",
        "pk": ["invoice_no", "line_no"],
        "columns": [
            _col("invoice_no", "Накладная", "int", required=True, fk=_fk("issues", "invoice_no", "customer")),
            _col("line_no", "Строка", "int", required=True),
            _col("nomenclature_no", "Номенклатурный номер", required=True),
            _col("sale_price", "Цена продажи", "real", required=True),
            _col("qty", "Количество", "real", required=True),
        ],
    },
    {
        "slug": "stock",
        "table": "stock",
        "title": "Остатки партий",
        "group": "Документы",
        "readonly": True,
        "pk": ["nomenclature_no"],
        "columns": [
            _col("nomenclature_no", "Номенклатурный номер"),
            _col("warehouse_no", "Склад", "int", fk=_fk("warehouses", "warehouse_no", "name")),
            _col("product_id", "Товар", "int", fk=_fk("products", "product_id", "name")),
            _col("purchase_price", "Цена закупки", "real"),
            _col("qty_in", "Приход", "real"),
            _col("qty_out", "Расход", "real"),
            _col("qty_left", "Остаток", "real"),
        ],
    },
]

VIEWS = [
    {
        "slug": "v-products",
        "table": "v_products",
        "title": "Товары (одна таблица)",
        "menu": "Каталог товаров",
        "group": "Представления",
        "readonly": True,
        "pk": ["product_id"],
        "columns": [
            _col("product_id", "Код", "int"),
            _col("sku", "Артикул"),
            _col("name", "Наименование"),
            _col("unit", "Единица"),
            _col("category", "Категория"),
        ],
    },
    {
        "slug": "v-staff",
        "table": "v_staff",
        "title": "Сотрудники со складом и должностью",
        "menu": "Сотрудники",
        "group": "Представления",
        "readonly": True,
        "pk": ["inn"],
        "columns": [
            _col("inn", "ИНН"),
            _col("full_name", "ФИО"),
            _col("hired_on", "Дата приёма", "date"),
            _col("phone", "Телефон"),
            _col("warehouse_no", "Номер склада", "int"),
            _col("warehouse_name", "Склад"),
            _col("position_title", "Должность"),
            _col("base_salary", "Оклад", "real"),
        ],
    },
    {
        "slug": "v-turnover",
        "table": "v_product_turnover",
        "title": "Товары с продажей от 10 единиц",
        "menu": "Оборот от 10 ед.",
        "group": "Представления",
        "readonly": True,
        "pk": ["product_id"],
        "columns": [
            _col("product_id", "Код", "int"),
            _col("product_name", "Товар"),
            _col("qty_sold", "Продано", "real"),
            _col("revenue", "Выручка", "real"),
        ],
    },
]

SPECS = TABLES + VIEWS
SPEC_BY_SLUG = {item["slug"]: item for item in SPECS}


def _names(spec, predicate):
    return [column["name"] for column in spec["columns"] if predicate(column)]


def searchable(spec):
    return [column["name"] for column in spec["columns"] if column["kind"] == "text" or column["name"] in spec["pk"]]


def sortable(spec):
    return [column["name"] for column in spec["columns"]]


def coerce(column, raw):
    if raw is None:
        raw = ""
    raw = str(raw).strip()
    if raw == "":
        if column.get("required") and not column.get("auto"):
            raise ValueError("Заполните поле «%s»." % column["label"])
        return None
    kind = column.get("kind", "text")
    if kind == "int":
        try:
            return int(raw)
        except ValueError:
            raise ValueError("Поле «%s» должно быть целым числом." % column["label"])
    if kind == "real":
        try:
            return float(raw.replace(" ", "").replace(",", "."))
        except ValueError:
            raise ValueError("Поле «%s» должно быть числом." % column["label"])
    return raw


def rows_to_dicts(rows):
    return [dict(row) for row in rows]


def fk_options(conn, column):
    fk = column["fk"]
    sql = "SELECT {value} AS v, {label} AS l FROM {table} ORDER BY 2".format(**fk)
    return rows_to_dicts(conn.execute(sql))


def list_rows(conn, spec, search_field, search, filter_field, filter_op, filter_value, sort, direction):
    columns = [column["name"] for column in spec["columns"]]
    allowed = set(columns)
    sql = "SELECT %s FROM %s" % (", ".join(columns), spec["table"])
    where = []
    params = []
    text_search = ""
    text_filter = ""
    if search and search_field in allowed:
        text_search = (search_field, search.strip().casefold())
    if filter_value not in (None, "") and filter_field in allowed:
        op = filter_op if filter_op in ("eq", "gt", "lt", "contains") else "contains"
        if op == "eq":
            where.append("%s = ?" % filter_field)
            params.append(filter_value.strip())
        elif op == "gt":
            where.append("%s > ?" % filter_field)
            params.append(filter_value.strip())
        elif op == "lt":
            where.append("%s < ?" % filter_field)
            params.append(filter_value.strip())
        else:
            text_filter = (filter_field, filter_value.strip().casefold())
    if where:
        sql += " WHERE " + " AND ".join(where)
    if sort not in allowed:
        sort = columns[0]
    sql += " ORDER BY %s %s" % (sort, "DESC" if direction == "desc" else "ASC")
    rows = rows_to_dicts(conn.execute(sql, params))
    if text_search:
        field, needle = text_search
        rows = [row for row in rows if needle in str(row.get(field) or "").casefold()]
    if text_filter:
        field, needle = text_filter
        rows = [row for row in rows if needle in str(row.get(field) or "").casefold()]
    return rows


def display_value(column, value, labels):
    if value is None:
        return ""
    if column["name"] in labels:
        label = labels[column["name"]].get(str(value))
        if label:
            return "%s — %s" % (value, label)
    kind = column.get("kind")
    if kind == "real":
        number = float(value)
        if column["name"] in ("price", "base_salary", "revenue", "purchase_price", "sale_price", "amount", "cost", "profit", "margin"):
            return format_money(number)
        return format_qty(number)
    return value


def format_money(value):
    if value is None or value == "":
        return ""
    return "{:,.2f}".format(float(value)).replace(",", " ")


def format_qty(value):
    if value is None or value == "":
        return ""
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return "{:.3f}".format(number).rstrip("0").rstrip(".")


def build_labels(conn, spec):
    labels = {}
    for column in spec["columns"]:
        if "fk" in column:
            labels[column["name"]] = {str(item["v"]): item["l"] for item in fk_options(conn, column)}
    return labels


def save_row(conn, spec, data, originals):
    if spec.get("readonly"):
        raise ValueError("Эта таблица только для просмотра.")
    values = {}
    for column in spec["columns"]:
        raw = data.get(column["name"])
        if column.get("auto") and str(raw or "").strip() == "":
            if originals is None:
                continue
            values[column["name"]] = originals[column["name"]]
            continue
        values[column["name"]] = coerce(column, raw)
    with conn:
        if originals is None:
            columns = list(values)
            sql = "INSERT INTO %s (%s) VALUES (%s)" % (
                spec["table"],
                ", ".join(columns),
                ", ".join("?" for _ in columns),
            )
            conn.execute(sql, [values[name] for name in columns])
            saved = {}
            for name in spec["pk"]:
                if name in values:
                    saved[name] = values[name]
                elif column_by_name(spec, name).get("auto"):
                    saved[name] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            return saved
        assignments = ", ".join("%s = ?" % name for name in values)
        where = " AND ".join("%s = ?" % name for name in spec["pk"])
        params = [values[name] for name in values] + [originals[name] for name in spec["pk"]]
        conn.execute(
            "UPDATE %s SET %s WHERE %s" % (spec["table"], assignments, where),
            params,
        )
        return {name: values[name] for name in spec["pk"]}


def column_by_name(spec, name):
    for column in spec["columns"]:
        if column["name"] == name:
            return column
    raise KeyError(name)


def delete_row(conn, spec, originals):
    if spec.get("readonly"):
        raise ValueError("Эту таблицу нельзя изменять: её ведут триггеры.")
    where = " AND ".join("%s = ?" % name for name in spec["pk"])
    params = [originals[name] for name in spec["pk"]]
    with conn:
        cursor = conn.execute("DELETE FROM %s WHERE %s" % (spec["table"], where), params)
        if cursor.rowcount == 0:
            raise ValueError("Запись не найдена.")


def parse_originals(spec, source):
    originals = {}
    for name in spec["pk"]:
        raw = source.get("original__" + name, source.get(name))
        originals[name] = coerce(column_by_name(spec, name), raw)
    return originals


def dashboard(conn):
    stock_value = conn.execute(
        "SELECT ROUND(COALESCE(SUM(qty_left * purchase_price), 0), 2) AS s FROM stock"
    ).fetchone()["s"]
    return {
        "warehouses": conn.execute("SELECT COUNT(*) AS c FROM warehouses").fetchone()["c"],
        "staff": conn.execute("SELECT COUNT(*) AS c FROM staff").fetchone()["c"],
        "products": conn.execute("SELECT COUNT(*) AS c FROM products").fetchone()["c"],
        "receipts": conn.execute("SELECT COUNT(*) AS c FROM receipts").fetchone()["c"],
        "issues": conn.execute("SELECT COUNT(*) AS c FROM issues").fetchone()["c"],
        "stock_value": stock_value,
    }


def next_number(conn, table, floor):
    row = conn.execute(
        "SELECT COALESCE(MAX(invoice_no), ?) + 1 AS n FROM %s" % table,
        (floor,),
    ).fetchone()
    return row["n"]


def product_choices(conn):
    return rows_to_dicts(
        conn.execute(
            """
            SELECT product_id AS id, sku, name, unit
            FROM products
            ORDER BY name
            """
        )
    )


def stock_choices(conn, warehouse_no, extra_noms=()):
    extra = [item for item in extra_noms if item]
    if extra:
        marks = ", ".join("?" for _ in extra)
        condition = "s.qty_left > 0 OR s.nomenclature_no IN (%s)" % marks
        params = [warehouse_no] + extra
    else:
        condition = "s.qty_left > 0"
        params = [warehouse_no]
    sql = """
        SELECT s.nomenclature_no AS nom,
               p.name AS name,
               p.unit AS unit,
               s.qty_left AS left_qty,
               s.purchase_price AS price
        FROM stock s
        JOIN products p ON p.product_id = s.product_id
        WHERE s.warehouse_no = ? AND (%s)
        ORDER BY p.name, s.nomenclature_no
    """ % condition
    return rows_to_dicts(conn.execute(sql, params))


def load_receipt(conn, invoice_no):
    header = conn.execute("SELECT * FROM receipts WHERE invoice_no = ?", (invoice_no,)).fetchone()
    if header is None:
        return None, []
    lines = conn.execute(
        """
        SELECT line_no, product_id, nomenclature_no, price, qty
        FROM receipt_lines
        WHERE invoice_no = ?
        ORDER BY line_no
        """,
        (invoice_no,),
    ).fetchall()
    return dict(header), rows_to_dicts(lines)


def load_issue(conn, invoice_no):
    header = conn.execute("SELECT * FROM issues WHERE invoice_no = ?", (invoice_no,)).fetchone()
    if header is None:
        return None, []
    lines = conn.execute(
        """
        SELECT line_no, nomenclature_no, sale_price, qty
        FROM issue_lines
        WHERE invoice_no = ?
        ORDER BY line_no
        """,
        (invoice_no,),
    ).fetchall()
    return dict(header), rows_to_dicts(lines)


def _clean_lines(lines):
    cleaned = []
    for line in lines:
        meaningful = any(str(line.get(key, "")).strip() for key in line if key != "line_no")
        if meaningful:
            cleaned.append(line)
    if not cleaned:
        raise ValueError("Добавьте хотя бы одну строку накладной.")
    return cleaned


def save_receipt(conn, header, lines, original_invoice):
    invoice = coerce(_col("invoice_no", "Накладная", "int", required=True), header.get("invoice_no"))
    warehouse = coerce(_col("warehouse_no", "Склад", "int", required=True), header.get("warehouse_no"))
    moment = coerce(_col("receipt_date", "Дата", "date", required=True), header.get("receipt_date"))
    supplier = coerce(_col("supplier", "Поставщик", required=True), header.get("supplier"))
    supplier_doc = coerce(_col("supplier_doc", "Документ поставщика"), header.get("supplier_doc"))
    prepared = []
    for line in _clean_lines(lines):
        prepared.append(
            {
                "line_no": line.get("line_no"),
                "product_id": coerce(_col("product_id", "Товар", "int", required=True), line.get("product_id")),
                "nomenclature_no": str(line.get("nomenclature_no") or "").strip(),
                "price": coerce(_col("price", "Цена", "real", required=True), line.get("price")),
                "qty": coerce(_col("qty", "Количество", "real", required=True), line.get("qty")),
            }
        )
    with conn:
        if original_invoice is None:
            conn.execute(
                """
                INSERT INTO receipts (invoice_no, warehouse_no, receipt_date, supplier, supplier_doc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (invoice, warehouse, moment, supplier, supplier_doc),
            )
        else:
            conn.execute(
                """
                UPDATE receipts
                SET invoice_no = ?, warehouse_no = ?, receipt_date = ?, supplier = ?, supplier_doc = ?
                WHERE invoice_no = ?
                """,
                (invoice, warehouse, moment, supplier, supplier_doc, original_invoice),
            )
        existing = {
            row["line_no"]: dict(row)
            for row in conn.execute(
                "SELECT * FROM receipt_lines WHERE invoice_no = ?",
                (invoice,),
            )
        }
        submitted_numbers = set()
        next_no = max(existing) + 1 if existing else 1
        normalized = []
        for line in prepared:
            number = str(line["line_no"] or "").strip()
            if number:
                number = int(number)
            else:
                number = next_no
                next_no += 1
            if number in submitted_numbers:
                number = next_no
                next_no += 1
            submitted_numbers.add(number)
            if not line["nomenclature_no"]:
                line["nomenclature_no"] = "%s-%s-%s" % (warehouse, invoice, number)
            line["line_no"] = number
            normalized.append(line)
        for number in list(existing):
            if number not in submitted_numbers:
                conn.execute(
                    "DELETE FROM receipt_lines WHERE invoice_no = ? AND line_no = ?",
                    (invoice, number),
                )
                existing.pop(number)
        for line in normalized:
            old = existing.get(line["line_no"])
            if old and (
                old["nomenclature_no"] != line["nomenclature_no"]
                or old["product_id"] != line["product_id"]
            ):
                conn.execute(
                    "DELETE FROM receipt_lines WHERE invoice_no = ? AND line_no = ?",
                    (invoice, line["line_no"]),
                )
                old = None
            if old:
                conn.execute(
                    """
                    UPDATE receipt_lines
                    SET price = ?, qty = ?
                    WHERE invoice_no = ? AND line_no = ?
                    """,
                    (line["price"], line["qty"], invoice, line["line_no"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO receipt_lines (
                        invoice_no, line_no, product_id, nomenclature_no, price, qty
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        invoice,
                        line["line_no"],
                        line["product_id"],
                        line["nomenclature_no"],
                        line["price"],
                        line["qty"],
                    ),
                )
    return invoice


def save_issue(conn, header, lines, original_invoice):
    invoice = coerce(_col("invoice_no", "Накладная", "int", required=True), header.get("invoice_no"))
    warehouse = coerce(_col("warehouse_no", "Склад", "int", required=True), header.get("warehouse_no"))
    moment = coerce(_col("issue_date", "Дата", "date", required=True), header.get("issue_date"))
    customer = coerce(_col("customer", "Покупатель", required=True), header.get("customer"))
    prepared = []
    for line in _clean_lines(lines):
        prepared.append(
            {
                "line_no": line.get("line_no"),
                "nomenclature_no": coerce(
                    _col("nomenclature_no", "Партия", required=True),
                    line.get("nomenclature_no"),
                ),
                "sale_price": coerce(_col("sale_price", "Цена продажи", "real", required=True), line.get("sale_price")),
                "qty": coerce(_col("qty", "Количество", "real", required=True), line.get("qty")),
            }
        )
    with conn:
        if original_invoice is None:
            conn.execute(
                "INSERT INTO issues (invoice_no, warehouse_no, issue_date, customer) VALUES (?, ?, ?, ?)",
                (invoice, warehouse, moment, customer),
            )
        else:
            conn.execute(
                """
                UPDATE issues
                SET invoice_no = ?, warehouse_no = ?, issue_date = ?, customer = ?
                WHERE invoice_no = ?
                """,
                (invoice, warehouse, moment, customer, original_invoice),
            )
        existing = {
            row["line_no"]: dict(row)
            for row in conn.execute(
                "SELECT * FROM issue_lines WHERE invoice_no = ?",
                (invoice,),
            )
        }
        submitted_numbers = set()
        next_no = max(existing) + 1 if existing else 1
        normalized = []
        for line in prepared:
            number = str(line["line_no"] or "").strip()
            if number:
                number = int(number)
            else:
                number = next_no
                next_no += 1
            if number in submitted_numbers:
                number = next_no
                next_no += 1
            submitted_numbers.add(number)
            line["line_no"] = number
            normalized.append(line)
        for number in list(existing):
            if number not in submitted_numbers:
                conn.execute(
                    "DELETE FROM issue_lines WHERE invoice_no = ? AND line_no = ?",
                    (invoice, number),
                )
                existing.pop(number)
        for line in normalized:
            old = existing.get(line["line_no"])
            if old and old["nomenclature_no"] != line["nomenclature_no"]:
                conn.execute(
                    "DELETE FROM issue_lines WHERE invoice_no = ? AND line_no = ?",
                    (invoice, line["line_no"]),
                )
                old = None
            if old:
                conn.execute(
                    """
                    UPDATE issue_lines
                    SET sale_price = ?, qty = ?
                    WHERE invoice_no = ? AND line_no = ?
                    """,
                    (line["sale_price"], line["qty"], invoice, line["line_no"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO issue_lines (
                        invoice_no, line_no, nomenclature_no, sale_price, qty
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        invoice,
                        line["line_no"],
                        line["nomenclature_no"],
                        line["sale_price"],
                        line["qty"],
                    ),
                )
    return invoice


def _order(sort, direction, allowed, default):
    if sort not in allowed:
        sort = default
    return sort, "DESC" if direction == "desc" else "ASC"


def _group(rows, group_key, sum_fields, ratio=None):
    groups = []
    current = None
    bucket = []

    def totals(items):
        result = {}
        for field in sum_fields:
            result[field] = 0.0
            for item in items:
                result[field] += float(item.get(field) or 0)
        if ratio:
            name, left, right = ratio
            result[name] = (result[left] / result[right] * 100.0) if result[right] else None
        return result

    for row in rows:
        key = row[group_key]
        if current is None:
            current = key
        if key != current:
            groups.append({"title": current, "rows": bucket, "totals": totals(bucket)})
            bucket = []
            current = key
        bucket.append(row)
    if current is not None:
        groups.append({"title": current, "rows": bucket, "totals": totals(bucket)})
    return groups, totals(rows)


def report_stock(conn, warehouse_no, category, name, only_positive, sort, direction):
    where = []
    params = []
    if warehouse_no:
        where.append("s.warehouse_no = ?")
        params.append(int(warehouse_no))
    if category:
        where.append("p.category = ?")
        params.append(category)
    if name:
        where.append("p.name LIKE ?")
        params.append("%" + name.strip() + "%")
    if only_positive:
        where.append("s.qty_left > 0")
    sort, direction = _order(sort, direction, {"product", "qty_left", "amount", "nomenclature"}, "product")
    sql = """
        SELECT w.name AS warehouse,
               p.name AS product,
               p.category AS category,
               p.unit AS unit,
               s.nomenclature_no AS nomenclature,
               s.purchase_price AS price,
               s.qty_in AS qty_in,
               s.qty_out AS qty_out,
               s.qty_left AS qty_left,
               ROUND(s.qty_left * s.purchase_price, 2) AS amount
        FROM stock s
        JOIN products p ON p.product_id = s.product_id
        JOIN warehouses w ON w.warehouse_no = s.warehouse_no
        {where}
        ORDER BY w.name, {sort} {direction}
    """.format(
        where=("WHERE " + " AND ".join(where)) if where else "",
        sort=sort,
        direction=direction,
    )
    rows = rows_to_dicts(conn.execute(sql, params))
    groups, grand = _group(rows, "warehouse", ["qty_left", "amount"])
    columns = [
        {"key": "nomenclature", "label": "Номенклатурный номер"},
        {"key": "product", "label": "Товар"},
        {"key": "category", "label": "Категория"},
        {"key": "unit", "label": "Ед."},
        {"key": "price", "label": "Цена закупки", "kind": "money"},
        {"key": "qty_in", "label": "Приход", "kind": "qty"},
        {"key": "qty_out", "label": "Расход", "kind": "qty"},
        {"key": "qty_left", "label": "Остаток", "kind": "qty"},
        {"key": "amount", "label": "Сумма остатка", "kind": "money"},
    ]
    return {"columns": columns, "groups": groups, "grand": grand, "count": len(rows)}


def report_profit(conn, warehouse_no, date_from, date_to, customer, product, sort, direction):
    where = []
    params = []
    if warehouse_no:
        where.append("i.warehouse_no = ?")
        params.append(int(warehouse_no))
    if date_from:
        where.append("i.issue_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("i.issue_date <= ?")
        params.append(date_to)
    if customer:
        where.append("i.customer LIKE ?")
        params.append("%" + customer.strip() + "%")
    if product:
        where.append("p.name LIKE ?")
        params.append("%" + product.strip() + "%")
    sort, direction = _order(sort, direction, {"doc_date", "product", "profit", "customer"}, "doc_date")
    sql = """
        SELECT w.name AS warehouse,
               i.issue_date AS doc_date,
               i.invoice_no AS invoice_no,
               i.customer AS customer,
               p.name AS product,
               l.nomenclature_no AS nomenclature,
               l.qty AS qty,
               s.purchase_price AS purchase_price,
               l.sale_price AS sale_price,
               ROUND(l.qty * l.sale_price, 2) AS revenue,
               ROUND(l.qty * s.purchase_price, 2) AS cost,
               ROUND(l.qty * (l.sale_price - s.purchase_price), 2) AS profit
        FROM issue_lines l
        JOIN issues i ON i.invoice_no = l.invoice_no
        JOIN stock s ON s.nomenclature_no = l.nomenclature_no
        JOIN products p ON p.product_id = s.product_id
        JOIN warehouses w ON w.warehouse_no = i.warehouse_no
        {where}
        ORDER BY w.name, {sort} {direction}
    """.format(
        where=("WHERE " + " AND ".join(where)) if where else "",
        sort=sort,
        direction=direction,
    )
    rows = rows_to_dicts(conn.execute(sql, params))
    for row in rows:
        cost = float(row["cost"] or 0)
        row["margin"] = (float(row["profit"]) / cost * 100.0) if cost else None
    groups, grand = _group(
        rows,
        "warehouse",
        ["qty", "revenue", "cost", "profit"],
        ratio=("margin", "profit", "cost"),
    )
    columns = [
        {"key": "doc_date", "label": "Дата"},
        {"key": "invoice_no", "label": "Накладная"},
        {"key": "customer", "label": "Покупатель"},
        {"key": "product", "label": "Товар"},
        {"key": "qty", "label": "Кол-во", "kind": "qty"},
        {"key": "purchase_price", "label": "Закупка", "kind": "money"},
        {"key": "sale_price", "label": "Продажа", "kind": "money"},
        {"key": "revenue", "label": "Выручка", "kind": "money"},
        {"key": "cost", "label": "Себестоимость", "kind": "money"},
        {"key": "profit", "label": "Прибыль", "kind": "money"},
        {"key": "margin", "label": "Рентабельность, %", "kind": "money"},
    ]
    return {"columns": columns, "groups": groups, "grand": grand, "count": len(rows)}


def report_suppliers(conn, warehouse_no, date_from, date_to, supplier, sort, direction):
    where = []
    params = []
    if warehouse_no:
        where.append("r.warehouse_no = ?")
        params.append(int(warehouse_no))
    if date_from:
        where.append("r.receipt_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("r.receipt_date <= ?")
        params.append(date_to)
    if supplier:
        where.append("r.supplier LIKE ?")
        params.append("%" + supplier.strip() + "%")
    sort, direction = _order(sort, direction, {"doc_date", "amount", "product", "supplier"}, "doc_date")
    sql = """
        SELECT r.supplier AS supplier,
               r.receipt_date AS doc_date,
               r.invoice_no AS invoice_no,
               w.name AS warehouse,
               p.name AS product,
               p.unit AS unit,
               l.qty AS qty,
               l.price AS price,
               ROUND(l.qty * l.price, 2) AS amount
        FROM receipt_lines l
        JOIN receipts r ON r.invoice_no = l.invoice_no
        JOIN products p ON p.product_id = l.product_id
        JOIN warehouses w ON w.warehouse_no = r.warehouse_no
        {where}
        ORDER BY r.supplier, {sort} {direction}
    """.format(
        where=("WHERE " + " AND ".join(where)) if where else "",
        sort=sort,
        direction=direction,
    )
    rows = rows_to_dicts(conn.execute(sql, params))
    groups, grand = _group(rows, "supplier", ["qty", "amount"])
    columns = [
        {"key": "doc_date", "label": "Дата"},
        {"key": "invoice_no", "label": "Накладная"},
        {"key": "warehouse", "label": "Склад"},
        {"key": "product", "label": "Товар"},
        {"key": "unit", "label": "Ед."},
        {"key": "qty", "label": "Количество", "kind": "qty"},
        {"key": "price", "label": "Цена", "kind": "money"},
        {"key": "amount", "label": "Сумма", "kind": "money"},
    ]
    return {"columns": columns, "groups": groups, "grand": grand, "count": len(rows)}


def categories(conn):
    return [row["category"] for row in conn.execute("SELECT DISTINCT category FROM products ORDER BY category")]


def warehouse_choices(conn):
    return rows_to_dicts(
        conn.execute("SELECT warehouse_no AS id, name FROM warehouses ORDER BY warehouse_no")
    )
