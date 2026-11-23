import sqlite3
from datetime import date

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

import db

app = Flask(__name__)
app.secret_key = "sklad-kursovaya"
app.config["TEMPLATES_AUTO_RELOAD"] = True

PREFILL = {
    "base_salary": "35000",
    "unit": "шт",
    "category": "Прочее",
}


@app.before_request
def open_db():
    g.db = db.connect()


@app.teardown_request
def close_db(_exc):
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


@app.template_filter("money")
def money_filter(value):
    return db.format_money(value)


@app.template_filter("qty")
def qty_filter(value):
    return db.format_qty(value)


@app.template_filter("cell")
def cell_filter(value, kind=None):
    if kind == "money":
        return db.format_money(value)
    if kind == "qty":
        return db.format_qty(value)
    if value is None:
        return ""
    return value


def spec_or_404(slug):
    spec = db.SPEC_BY_SLUG.get(slug)
    if spec is None:
        abort(404)
    return spec


def query_params():
    return {
        "q": request.values.get("q", ""),
        "qfield": request.values.get("qfield", ""),
        "ffield": request.values.get("ffield", ""),
        "fop": request.values.get("fop", "contains"),
        "fval": request.values.get("fval", ""),
        "sort": request.values.get("sort", ""),
        "dir": request.values.get("dir", "asc"),
    }


def table_url(slug, **extra):
    params = query_params()
    params.update(extra)
    return url_for("table_view", slug=slug, **params)


def form_values(spec, source, blank):
    values = {}
    for column in spec["columns"]:
        if source is not None and not blank:
            raw = source.get(column["name"], "")
            if raw is None:
                raw = ""
            elif column.get("kind") == "real":
                if column["name"] in ("price", "base_salary", "revenue", "purchase_price", "sale_price", "amount", "cost", "profit", "margin"):
                    raw = "{:.2f}".format(float(raw))
                else:
                    raw = db.format_qty(raw)
            values[column["name"]] = raw
        else:
            if column.get("kind") == "date":
                values[column["name"]] = date.today().isoformat()
            else:
                values[column["name"]] = PREFILL.get(column["name"], "")
    return values


@app.route("/")
def home():
    return render_template("home.html", stats=db.dashboard(g.db), today=date.today().isoformat())


@app.route("/table/<slug>", methods=["GET", "POST"])
def table_view(slug):
    spec = spec_or_404(slug)
    params = query_params()
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "delete":
                db.delete_row(g.db, spec, db.parse_originals(spec, request.form))
                flash("Запись удалена.")
                return redirect(table_url(slug, rec=0))
            originals = None
            if request.form.get("mode") == "edit":
                originals = db.parse_originals(spec, request.form)
            saved = db.save_row(g.db, spec, request.form, originals)
            flash("Запись сохранена.")
            rows = db.list_rows(g.db, spec, params["qfield"], params["q"], params["ffield"], params["fop"], params["fval"], params["sort"], params["dir"])
            index = 0
            for i, row in enumerate(rows):
                if all(str(row[name]) == str(saved[name]) for name in spec["pk"]):
                    index = i
                    break
            return redirect(table_url(slug, rec=index))
        except (sqlite3.Error, ValueError) as error:
            flash(db.humanize(error), "error")

    rows = db.list_rows(
        g.db, spec,
        params["qfield"], params["q"],
        params["ffield"], params["fop"], params["fval"],
        params["sort"], params["dir"],
    )
    labels = db.build_labels(g.db, spec)
    shown = []
    for row in rows:
        shown.append({name: db.display_value(column, row[name], labels) for name, column in ((c["name"], c) for c in spec["columns"])})
    rec = request.values.get("rec", "0")
    blank = rec == "new" or (request.method == "POST" and request.form.get("mode") == "new")
    index = 0
    if rows and not blank:
        try:
            index = int(rec)
        except ValueError:
            index = 0
        index = max(0, min(index, len(rows) - 1))
    current = None if blank or not rows else rows[index]
    if request.method == "POST" and request.form.get("action") == "save":
        values = {column["name"]: request.form.get(column["name"], "") for column in spec["columns"]}
    else:
        values = form_values(spec, current, blank or current is None)
    fk = {}
    for column in spec["columns"]:
        if "fk" in column:
            fk[column["name"]] = db.fk_options(g.db, column)
    return render_template(
        "table.html",
        spec=spec,
        rows=rows,
        shown=shown,
        index=index,
        blank=blank or current is None,
        values=values,
        fk=fk,
        params=params,
        total=len(rows),
    )


@app.route("/receipt/new", methods=["GET", "POST"])
@app.route("/receipt/<int:invoice_no>", methods=["GET", "POST"])
def receipt_edit(invoice_no=None):
    return document_edit("receipt", invoice_no)


@app.route("/issue/new", methods=["GET", "POST"])
@app.route("/issue/<int:invoice_no>", methods=["GET", "POST"])
def issue_edit(invoice_no=None):
    return document_edit("issue", invoice_no)


def document_edit(kind, invoice_no):
    is_new = invoice_no is None
    if request.method == "POST":
        header = request.form
        if kind == "receipt":
            lines = posted_lines(request.form, ["line_no", "product_id", "nomenclature_no", "price", "qty"])
            saver = db.save_receipt
            target = "receipt_edit"
        else:
            lines = posted_lines(request.form, ["line_no", "nomenclature_no", "sale_price", "qty"])
            saver = db.save_issue
            target = "issue_edit"
        original = request.form.get("original_invoice") or None
        original = int(original) if original else None
        try:
            saved = saver(g.db, header, lines, original)
            flash("Накладная сохранена. Шапка и строки записаны в связанные таблицы.")
            return redirect(url_for(target, invoice_no=saved))
        except (sqlite3.Error, ValueError) as error:
            flash(db.humanize(error), "error")
            header_data, line_data = header_from_form(kind, header, lines)
            return render_document(kind, header_data, line_data, is_new=original is None, failed=True, original_invoice=original)

    if is_new:
        if kind == "receipt":
            header = {
                "invoice_no": db.next_number(g.db, "receipts", 1000),
                "warehouse_no": 1,
                "receipt_date": date.today().isoformat(),
                "supplier": "",
                "supplier_doc": "",
            }
        else:
            header = {
                "invoice_no": db.next_number(g.db, "issues", 2000),
                "warehouse_no": 1,
                "issue_date": date.today().isoformat(),
                "customer": "",
            }
        lines = [empty_line(kind)]
        return render_document(kind, header, lines, is_new=True, failed=False, original_invoice=None)

    if kind == "receipt":
        header, lines = db.load_receipt(g.db, invoice_no)
    else:
        header, lines = db.load_issue(g.db, invoice_no)
    if header is None:
        abort(404)
    return render_document(kind, header, lines, is_new=False, failed=False, original_invoice=invoice_no)


def header_from_form(kind, form, lines):
    if kind == "receipt":
        header = {
            "invoice_no": form.get("invoice_no", ""),
            "warehouse_no": form.get("warehouse_no", ""),
            "receipt_date": form.get("receipt_date", ""),
            "supplier": form.get("supplier", ""),
            "supplier_doc": form.get("supplier_doc", ""),
        }
    else:
        header = {
            "invoice_no": form.get("invoice_no", ""),
            "warehouse_no": form.get("warehouse_no", ""),
            "issue_date": form.get("issue_date", ""),
            "customer": form.get("customer", ""),
        }
    return header, lines


def empty_line(kind):
    if kind == "receipt":
        return {"line_no": "", "product_id": "", "nomenclature_no": "", "price": "", "qty": ""}
    return {"line_no": "", "nomenclature_no": "", "sale_price": "", "qty": ""}


def posted_lines(form, keys):
    lists = {key: form.getlist(key) for key in keys}
    count = max((len(values) for values in lists.values()), default=0)
    lines = []
    for index in range(count):
        lines.append({key: (lists[key][index] if index < len(lists[key]) else "") for key in keys})
    return lines


def render_document(kind, header, lines, is_new, failed, original_invoice):
    warehouse_id = header.get("warehouse_no") or 1
    try:
        warehouse_id = int(warehouse_id)
    except (TypeError, ValueError):
        warehouse_id = 1
    extra = []
    if kind == "issue":
        extra = [line.get("nomenclature_no") for line in lines if line.get("nomenclature_no")]
    return render_template(
        "document.html",
        kind=kind,
        header=header,
        lines=lines,
        is_new=is_new,
        failed=failed,
        original_invoice=original_invoice,
        warehouses=db.warehouse_choices(g.db),
        products=db.product_choices(g.db),
        stock=db.stock_choices(g.db, warehouse_id, extra),
    )


@app.route("/receipt/<int:invoice_no>/delete", methods=["POST"])
def receipt_delete(invoice_no):
    try:
        with g.db:
            g.db.execute("DELETE FROM receipts WHERE invoice_no = ?", (invoice_no,))
        flash("Приходная накладная удалена.")
        return redirect(url_for("table_view", slug="receipts"))
    except sqlite3.Error as error:
        flash(db.humanize(error), "error")
        return redirect(url_for("receipt_edit", invoice_no=invoice_no))


@app.route("/issue/<int:invoice_no>/delete", methods=["POST"])
def issue_delete(invoice_no):
    try:
        with g.db:
            g.db.execute("DELETE FROM issues WHERE invoice_no = ?", (invoice_no,))
        flash("Расходная накладная удалена.")
        return redirect(url_for("table_view", slug="issues"))
    except sqlite3.Error as error:
        flash(db.humanize(error), "error")
        return redirect(url_for("issue_edit", invoice_no=invoice_no))


@app.route("/api/stock/<int:warehouse_no>")
def api_stock(warehouse_no):
    return jsonify(db.stock_choices(g.db, warehouse_no))


@app.route("/report/<slug>")
def report_view(slug):
    reports = {
        "stock": "Остатки на складе",
        "profit": "Прибыль от реализации",
        "suppliers": "Приход по поставщикам",
    }
    if slug not in reports:
        abort(404)
    show = request.args.get("show") == "1"
    result = None
    if show:
        if slug == "stock":
            result = db.report_stock(
                g.db,
                request.args.get("warehouse") or None,
                request.args.get("category") or "",
                request.args.get("name") or "",
                request.args.get("only_positive") == "1",
                request.args.get("sort") or "product",
                request.args.get("dir") or "asc",
            )
        elif slug == "profit":
            result = db.report_profit(
                g.db,
                request.args.get("warehouse") or None,
                request.args.get("date_from") or "",
                request.args.get("date_to") or "",
                request.args.get("customer") or "",
                request.args.get("product") or "",
                request.args.get("sort") or "doc_date",
                request.args.get("dir") or "asc",
            )
        else:
            result = db.report_suppliers(
                g.db,
                request.args.get("warehouse") or None,
                request.args.get("date_from") or "",
                request.args.get("date_to") or "",
                request.args.get("supplier") or "",
                request.args.get("sort") or "doc_date",
                request.args.get("dir") or "asc",
            )
    return render_template(
        "report.html",
        slug=slug,
        title=reports[slug],
        show=show,
        result=result,
        warehouses=db.warehouse_choices(g.db),
        categories=db.categories(g.db),
        args=request.args,
    )


@app.context_processor
def inject_nav():
    return {"tables": db.TABLES, "views": db.VIEWS}


if __name__ == "__main__":
    db.init_db()
    app.run(host="127.0.0.1", port=5000, debug=False)
