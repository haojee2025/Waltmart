from decimal import Decimal, InvalidOperation
from pathlib import Path
import os

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

from db import get_conn

# load env + Flask
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET", "dev")
CORS(app, supports_credentials=True)

# DEMO: fake current user (customer1)
def current_user_id() -> int:
    return 2  # customer1 seeded above

@app.get("/health")
def health():
    return jsonify(ok=True)

@app.get("/")
def home():
    # show wallet + products list
    with get_conn() as c, c.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT wallet_balance FROM users WHERE id=%s", (current_user_id(),))
        bal = cur.fetchone()
        cur.execute("SELECT id, name, spec, price FROM products ORDER BY id;")
        products = cur.fetchall()
    return render_template("index.html",
                           balance=bal["wallet_balance"] if bal else Decimal("0.00"),
                           products=products)

@app.route("/topup", methods=["GET", "POST"])
def topup():
    if request.method == "POST":
        raw = (request.form.get("amount") or "").strip()
        try:
            amt = Decimal(raw)
        except (InvalidOperation, ValueError):
            return render_template("topup.html", message="Please enter a valid number.", error=True)
        if amt <= 0:
            return render_template("topup.html", message="Amount must be > 0.", error=True)
        if amt > Decimal("100"):
            return render_template("topup.html", message="Max top-up is 100.", error=True)

        with get_conn() as c, c.cursor(cursor_factory=RealDictCursor) as cur:
            # lock user row
            cur.execute("SELECT id, wallet_balance FROM users WHERE id=%s FOR UPDATE;", (current_user_id(),))
            user = cur.fetchone()
            if not user:
                return render_template("topup.html", message="User not found.", error=True)

            new_balance = (Decimal(user["wallet_balance"]) + amt).quantize(Decimal("0.01"))
            # update + ledger in one tx
            cur.execute("UPDATE users SET wallet_balance=%s WHERE id=%s;", (str(new_balance), current_user_id()))
            cur.execute("""
                INSERT INTO wallet_transactions (user_id, kind, amount, balance_after)
                VALUES (%s,'TOP_UP',%s,%s);
            """, (current_user_id(), str(amt), str(new_balance)))
            c.commit()

        return render_template("topup.html", message=f"Top-up OK: {amt:.2f}", error=False)

    return render_template("topup.html")

# JSON: wallet balance
@app.get("/wallet")
def wallet_me():
    with get_conn() as c, c.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT wallet_balance FROM users WHERE id=%s", (current_user_id(),))
        row = cur.fetchone()
    return jsonify(balance=float(row["wallet_balance"]) if row else 0.0)

# JSON: products list (supports ?q=)
@app.get("/products")
def products_list():
    q = (request.args.get("q") or "").strip()
    with get_conn() as c, c.cursor(cursor_factory=RealDictCursor) as cur:
        if q:
            cur.execute("""SELECT id, name, spec, price FROM products
                           WHERE name ILIKE %s ORDER BY id;""", (f"%{q}%",))
        else:
            cur.execute("SELECT id, name, spec, price FROM products ORDER BY id;")
        rows = cur.fetchall()
    return jsonify(rows)

# JSON: create order (wallet debit + confirm)
@app.post("/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    items = data.get("items") or []
    if not items:
        return jsonify(error="items required"), 400

    with get_conn() as c, c.cursor(cursor_factory=RealDictCursor) as cur:
        # compute total using DB prices
        total = Decimal("0.00")
        cart = []
        for it in items:
            pid = int(it.get("product_id"))
            qty = int(it.get("qty", 1))
            if qty <= 0:
                return jsonify(error="qty must be > 0"), 400
            cur.execute("SELECT id, price FROM products WHERE id=%s", (pid,))
            p = cur.fetchone()
            if not p:
                return jsonify(error=f"product {pid} not found"), 404
            subtotal = (Decimal(p["price"]) * qty).quantize(Decimal("0.01"))
            total += subtotal
            cart.append((pid, qty, p["price"], subtotal))

        # lock user, check funds
        cur.execute("SELECT id, wallet_balance FROM users WHERE id=%s FOR UPDATE;", (current_user_id(),))
        u = cur.fetchone()
        if not u:
            return jsonify(error="user not found"), 404
        if Decimal(u["wallet_balance"]) < total:
            return jsonify(error="Insufficient wallet balance"), 402

        # create order
        cur.execute("INSERT INTO orders (user_id, status, total) VALUES (%s,'CONFIRMED',%s) RETURNING id;",
                    (current_user_id(), str(total)))
        order_id = cur.fetchone()["id"]

        # items
        for pid, qty, price_each, subtotal in cart:
            cur.execute("""
                INSERT INTO order_items (order_id, product_id, qty, price_each, subtotal)
                VALUES (%s,%s,%s,%s,%s);
            """, (order_id, pid, qty, str(price_each), str(subtotal)))

        # debit wallet + ledger
        new_balance = (Decimal(u["wallet_balance"]) - total).quantize(Decimal("0.01"))
        cur.execute("UPDATE users SET wallet_balance=%s WHERE id=%s;", (str(new_balance), current_user_id()))
        cur.execute("""
            INSERT INTO wallet_transactions (user_id, kind, amount, balance_after, order_id)
            VALUES (%s,'DEBIT',%s,%s,%s);
        """, (current_user_id(), str(total), str(new_balance), order_id))

        c.commit()

    return jsonify(order_id=order_id, status="CONFIRMED", charged=float(total), wallet_balance=float(new_balance)), 201

if __name__ == "__main__":
    app.run(port=5000, debug=True)
