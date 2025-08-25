import os
from pathlib import Path
from decimal import Decimal
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

# load .env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_USER = os.getenv("PG_USER", "postgres")
PG_PASSWORD = os.getenv("PG_PASSWORD", "root")
PG_DATABASE = os.getenv("PG_DATABASE", "grocery")

def conn(dbname: str):
    return psycopg2.connect(
        dbname=dbname, user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT
    )

def ensure_database():
    with conn("postgres") as c:
        c.autocommit = True
        with c.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (PG_DATABASE,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{PG_DATABASE}"')
                print(f'✅ Created database "{PG_DATABASE}"')
            else:
                print(f'ℹ️ Database "{PG_DATABASE}" already exists')

def ensure_schema_and_seed():
    with conn(PG_DATABASE) as c, c.cursor(cursor_factory=RealDictCursor) as cur:
        # tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
              id SERIAL PRIMARY KEY,
              role TEXT NOT NULL DEFAULT 'customer',
              name TEXT NOT NULL,
              email TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              phone TEXT,
              gender TEXT,
              dob DATE,
              address TEXT,
              wallet_balance NUMERIC(12,2) NOT NULL DEFAULT 100.00,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
              id SERIAL PRIMARY KEY,
              name TEXT NOT NULL,
              spec TEXT,
              price NUMERIC(10,2) NOT NULL,
              exp_date DATE,
              image_url TEXT,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
              id SERIAL PRIMARY KEY,
              user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              status TEXT NOT NULL DEFAULT 'CONFIRMED',
              total NUMERIC(10,2) NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
              id SERIAL PRIMARY KEY,
              order_id INT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
              product_id INT NOT NULL REFERENCES products(id),
              qty INT NOT NULL,
              price_each NUMERIC(10,2),
              subtotal NUMERIC(10,2)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wallet_transactions (
              id SERIAL PRIMARY KEY,
              user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              kind TEXT NOT NULL,         -- TOP_UP / DEBIT / REFUND / ADJUST
              amount NUMERIC(12,2) NOT NULL,
              balance_after NUMERIC(12,2) NOT NULL,
              order_id INT REFERENCES orders(id),
              created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
        """)
        print("✅ Tables ensured")

        # users
        pw = generate_password_hash("password")
        cur.execute("SELECT COUNT(*) FROM users;")
        if cur.fetchone()["count"] == 0:
            cur.execute("""
                INSERT INTO users (role, name, email, password_hash, phone, address) VALUES
                ('admin','Admin User','admin@grocery.local',%s,'0123456789','HQ Office'),
                ('customer','Demo Customer','customer1@grocery.local',%s,'0198765432','123 Demo Street'),
                ('customer','Second Customer','customer2@grocery.local',%s,'0188888888','456 Second Ave');
            """, (pw, pw, pw))
            print("✅ Seeded users (1 admin, 2 customers)")
        else:
            print("ℹ️ Users already present, skipping seed")

        # products
        cur.execute("SELECT COUNT(*) FROM products;")
        if cur.fetchone()["count"] == 0:
            cur.execute("""
                INSERT INTO products (name, spec, price) VALUES
                ('Apple','Fresh Red Apple', 1.50),
                ('Banana','Cavendish Banana', 2.00),
                ('Milk','1L Full Cream Milk', 4.90);
            """)
            print("✅ Seeded products")
        else:
            print("ℹ️ Products already present, skipping seed")

        # sample order for customer1 (2x Apple + 1x Banana)
        cur.execute("SELECT id, wallet_balance FROM users WHERE email=%s", ("customer1@grocery.local",))
        c1 = cur.fetchone()
        cur.execute("SELECT id, price FROM products WHERE name='Apple' LIMIT 1;")
        apple = cur.fetchone()
        cur.execute("SELECT id, price FROM products WHERE name='Banana' LIMIT 1;")
        banana = cur.fetchone()
        if c1 and apple and banana:
            cur.execute("SELECT 1 FROM orders WHERE user_id=%s LIMIT 1;", (c1["id"],))
            if not cur.fetchone():
                oi1_sub = Decimal(apple["price"]) * 2
                oi2_sub = Decimal(banana["price"]) * 1
                total = (oi1_sub + oi2_sub).quantize(Decimal("0.01"))

                cur.execute(
                    "INSERT INTO orders (user_id, status, total) VALUES (%s,'CONFIRMED',%s) RETURNING id;",
                    (c1["id"], str(total))
                )
                order_id = cur.fetchone()["id"]

                cur.execute("""
                    INSERT INTO order_items (order_id, product_id, qty, price_each, subtotal)
                    VALUES 
                      (%s,%s,2,%s,%s),
                      (%s,%s,1,%s,%s);
                """, (order_id, apple["id"], apple["price"], str(oi1_sub),
                      order_id, banana["id"], banana["price"], str(oi2_sub)))

                new_balance = (Decimal(c1["wallet_balance"]) - total).quantize(Decimal("0.01"))
                cur.execute("UPDATE users SET wallet_balance=%s WHERE id=%s;", (str(new_balance), c1["id"]))
                cur.execute("""
                    INSERT INTO wallet_transactions (user_id, kind, amount, balance_after, order_id)
                    VALUES (%s,'DEBIT',%s,%s,%s);
                """, (c1["id"], str(total), str(new_balance), order_id))

                print(f"✅ Seeded one order (order_id={order_id}, total={total})")
            else:
                print("ℹ️ Sample order exists, skipping")

        c.commit()

if __name__ == "__main__":
    ensure_database()
    ensure_schema_and_seed()
    print("🎉 DB ready")
