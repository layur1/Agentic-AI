"""
One-time (or re-run-to-reset) script to create the database/table and
seed sample product data into MySQL.

Product names here intentionally match the products described in
data/product_manuals.pdf, so cross-source questions (e.g. "price and
warranty of Laptop A") resolve correctly across both tools.

Run:
    python seed_mysql.py
"""
import mysql.connector
import config

SAMPLE_PRODUCTS = [
    ("Laptop A", 250000.00, 18, "Electronics"),
    ("Laptop B", 190000.00, 32, "Electronics"),
    ("Wireless Mouse M1", 4500.00, 120, "Accessories"),
    ("Bluetooth Speaker S2", 12500.00, 45, "Accessories"),
]


def seed():
    conn = mysql.connector.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
    )
    cursor = conn.cursor()

    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config.MYSQL_DATABASE}")
    cursor.execute(f"USE {config.MYSQL_DATABASE}")

    # Drop and recreate to guarantee the schema always matches this script,
    # even if an older/different 'products' table already exists.
    cursor.execute("DROP TABLE IF EXISTS products")
    cursor.execute("""
        CREATE TABLE products (
            id INT AUTO_INCREMENT PRIMARY KEY,
            product_name VARCHAR(255) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            stock INT NOT NULL,
            category VARCHAR(100) NOT NULL
        )
    """)

    cursor.executemany(
        "INSERT INTO products (product_name, price, stock, category) VALUES (%s, %s, %s, %s)",
        SAMPLE_PRODUCTS,
    )
    conn.commit()

    print(f"Seeded {len(SAMPLE_PRODUCTS)} products into "
          f"'{config.MYSQL_DATABASE}.products' at {config.MYSQL_HOST}:{config.MYSQL_PORT}")
    for name, price, stock, category in SAMPLE_PRODUCTS:
        print(f"  - {name}: Rs. {price:,.2f}, stock {stock}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    seed()