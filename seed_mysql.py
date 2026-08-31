"""
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

SAMPLE_USERS = [
    ("John Perera", "No. 45, Galle Road, Colombo 03"),
    ("John Fernando", "No. 30, Baseline Road, Colombo 09"),
    ("Amaya Silva", "No. 12, Kandy Road, Kadawatha"),
    ("Nadeesha Fernando", "No. 78, Negombo Road, Wattala"),
    ("Ruwan Jayasuriya", "No. 23, High Level Road, Nugegoda"),
    ("Kasun Bandara", "No. 9, Main Street, Matara"),
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

    # --- products table ---
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

    # --- users table ---
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("""
        CREATE TABLE users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            address VARCHAR(500) NOT NULL
        )
    """)
    cursor.executemany(
        "INSERT INTO users (name, address) VALUES (%s, %s)",
        SAMPLE_USERS,
    )

    conn.commit()

    print(f"Seeded {len(SAMPLE_PRODUCTS)} products and {len(SAMPLE_USERS)} users into "
          f"'{config.MYSQL_DATABASE}' at {config.MYSQL_HOST}:{config.MYSQL_PORT}")
    print("\nProducts:")
    for name, price, stock, category in SAMPLE_PRODUCTS:
        print(f"  - {name}: Rs. {price:,.2f}, stock {stock}")
    print("\nUsers:")
    for name, address in SAMPLE_USERS:
        print(f"  - {name}: {address}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    seed()