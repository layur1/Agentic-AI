"""
Direct SQL-injection safety test — bypasses the LLM entirely and calls
the database query logic directly, mirroring the exact pattern used in
mcp_servers/mysql_server.py's get_price().

Run from the project root:
    python testing/test_sql_injection_direct.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
import config

INJECTION_PAYLOADS = [
    "Laptop A'; DROP TABLE products; --",
    "' OR '1'='1",
    "Laptop A' UNION SELECT username, password FROM users --",
    "'; DELETE FROM products WHERE '1'='1",
]


def get_connection():
    return mysql.connector.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
    )


def count_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM products")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count


def run_query_with_payload(payload):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT product_name, price FROM products WHERE product_name LIKE %s LIMIT 1",
        (f"%{payload}%",),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row


def main():
    print("Checking baseline row count in 'products' table...")
    before_count = count_products()
    print(f"  Rows before test: {before_count}\n")

    for payload in INJECTION_PAYLOADS:
        print(f"--- Testing payload: {payload!r} ---")
        try:
            result = run_query_with_payload(payload)
            print(f"  Query executed safely. Result: {result}")
        except mysql.connector.Error as e:
            print(f"  MySQL raised an error (not necessarily a vulnerability, "
                  f"could just mean no match): {e}")
        print()

    print("Re-checking row count after all injection attempts...")
    after_count = count_products()
    print(f"  Rows after test: {after_count}\n")

    if before_count == after_count:
        print(f"PASS: Row count unchanged ({before_count} -> {after_count}). "
              f"Parameterised queries neutralised all {len(INJECTION_PAYLOADS)} injection payloads.")
    else:
        print(f"FAIL: Row count changed ({before_count} -> {after_count})! "
              f"This would indicate a real SQL injection vulnerability — investigate immediately.")


if __name__ == "__main__":
    main()