"""
Purchase Ledger: a small local web app for recording purchases.
All data stays on this computer, in data/ledger.json.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5050 in your browser.
"""
import json
import os
import re
import shutil
import threading
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "ledger.json"
BACKUP_DIR = DATA_DIR / "backups"
KEEP_BACKUPS = 30  # one backup per day, oldest removed after this many
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
lock = threading.Lock()


class DataFileError(Exception):
    pass


# ---------- storage ----------

def load():
    if not DATA_FILE.exists():
        return {"catalog": {"categories": [], "products": []}, "purchases": {}}
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise DataFileError(
            f"data/ledger.json is not valid JSON ({e}). Restore a copy from data/backups/."
        )
    data.setdefault("catalog", {"categories": [], "products": []})
    data.setdefault("purchases", {})
    return migrate(data)


def migrate(data):
    """Convert files from the first version (products with parts) to
    categories with products. Purchase lines get "category" + "product".
    Payment moves from the purchase onto each line ("paid", "paidDate").
    Lines without a delivery status start as "ordered"."""
    cat = data.get("catalog") or {}
    if "categories" not in cat:
        categories, products = [], []
        for p in cat.get("products", []):
            categories.append({"id": p.get("id"), "name": p.get("name", "")})
            for pt in p.get("parts", []):
                products.append({
                    "id": pt.get("id"), "name": pt.get("name", ""), "categoryId": p.get("id"),
                    "unit": pt.get("unit", ""), "qty": pt.get("qty", 1), "refPrice": pt.get("refPrice"),
                })
        data["catalog"] = {"categories": categories, "products": products}
    for body in data["purchases"].values():
        was_paid = bool(body.pop("paid", False))
        paid_date = body.pop("paidDate", None)
        lines = []
        for line in body.get("lines", []):
            if "part" in line and "category" not in line:
                line = {**line, "category": line.get("product", ""), "product": line.get("part", "")}
                line.pop("part", None)
            if "paid" not in line:
                line = {**line, "paid": was_paid, "paidDate": paid_date if was_paid else None}
            if "delivery" not in line:
                line = {**line, "delivery": "ordered", "eta": None, "deliveredDate": None}
            lines.append(line)
        body["lines"] = lines
    return data


def backup_once_a_day():
    if not DATA_FILE.exists():
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"ledger-{date.today().isoformat()}.json"
    if not target.exists():
        shutil.copy2(DATA_FILE, target)
        for old in sorted(BACKUP_DIR.glob("ledger-*.json"))[:-KEEP_BACKUPS]:
            old.unlink()


def save(data):
    DATA_DIR.mkdir(exist_ok=True)
    backup_once_a_day()
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DATA_FILE)


def error(msg, code):
    return jsonify({"error": msg}), code


@app.errorhandler(DataFileError)
def bad_data_file(e):
    return error(str(e), 500)


# ---------- routes ----------

@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/data")
def get_data():
    with lock:
        data = load()
    purchases = [{**body, "id": pid} for pid, body in data["purchases"].items()]
    return jsonify({"catalog": data["catalog"], "purchases": purchases})


@app.put("/api/catalog")
def put_catalog():
    body = request.get_json(silent=True)
    if (not isinstance(body, dict) or not isinstance(body.get("products"), list)
            or not isinstance(body.get("categories"), list)):
        return error("Invalid product list", 400)
    with lock:
        data = load()
        data["catalog"] = body
        save(data)
    return jsonify({"ok": True})


@app.put("/api/purchases/<pid>")
def put_purchase(pid):
    if not ID_RE.match(pid):
        return error("Invalid purchase id", 400)
    body = request.get_json(silent=True)
    if not valid_purchase(body):
        return error("Invalid purchase", 400)
    body.pop("id", None)
    with lock:
        data = load()
        data["purchases"][pid] = body
        save(data)
    return jsonify({"ok": True})


def valid_purchase(body):
    return isinstance(body, dict) and isinstance(body.get("date"), str) and isinstance(body.get("lines"), list)


@app.post("/api/purchases/batch")
def put_purchases_batch():
    """Save several purchases at once (used when marking many as paid)."""
    items = (request.get_json(silent=True) or {}).get("purchases")
    if not isinstance(items, list) or not items:
        return error("Nothing to save", 400)
    for item in items:
        if not valid_purchase(item) or not isinstance(item.get("id"), str) or not ID_RE.match(item["id"]):
            return error("Invalid purchase in batch", 400)
    with lock:
        data = load()
        for item in items:
            body = dict(item)
            data["purchases"][body.pop("id")] = body
        save(data)
    return jsonify({"ok": True})


@app.delete("/api/purchases/<pid>")
def delete_purchase(pid):
    with lock:
        data = load()
        if data["purchases"].pop(pid, None) is not None:
            save(data)
    return jsonify({"ok": True})


if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5050"))
    print(f"Purchase Ledger is running at http://{host}:{port}")
    print(f"Data file: {DATA_FILE}")
    app.run(host=host, port=port)
