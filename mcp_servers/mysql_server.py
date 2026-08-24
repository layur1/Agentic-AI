"""
FastMCP server exposing MySQL product, user, and delivery data as tools.

Includes schedule_delivery(customer_name, product_name, delivery_date) — a
genuine THREE-required-parameter tool, added to demonstrate and test
multi-parameter clarification handling, including the case where an
individual parameter (customer name, product name) is itself ambiguous.

Run standalone for debugging:
    python mcp_servers/mysql_server.py
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
import mysql.connector

import config

mcp = FastMCP("mysql-server")


def _get_connection():
    return mysql.connector.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
    )


@mcp.tool()
def get_price(product_name: str) -> str:
    """
    Get the current price of a product by name.

    Use this for questions about cost, price, or "how much does X cost" —
    this is live, frequently-changing data stored in the database, not
    the PDF documentation.

    IMPORTANT: This tool requires a product name. If the question doesn't
    name a specific product, do not call this tool — ask the user which
    product they mean and wait for their reply.

    Args:
        product_name: The exact or approximate product name, e.g. "Laptop A".

    Returns:
        The current price, or a not-found message.
    """
    conn = _get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT product_name, price FROM products WHERE product_name LIKE %s LIMIT 1",
        (f"%{product_name}%",),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return f"No product found matching '{product_name}'."
    return f"{row['product_name']}: Rs. {row['price']:,.2f}"


@mcp.tool()
def check_stock(product_name: str) -> str:
    """
    Check current inventory / stock level for a product.

    IMPORTANT: This tool requires a product name. If the question doesn't
    name a specific product, do not call this tool — ask the user which
    product they mean and wait for their reply.

    Args:
        product_name: The exact or approximate product name, e.g. "Laptop A".

    Returns:
        The current stock count, or a not-found message.
    """
    conn = _get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT product_name, stock FROM products WHERE product_name LIKE %s LIMIT 1",
        (f"%{product_name}%",),
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return f"No product found matching '{product_name}'."
    status = "In stock" if row["stock"] > 0 else "Out of stock"
    return f"{row['product_name']}: {status} ({row['stock']} units)"


@mcp.tool()
def search_products(query: str) -> str:
    """
    Search products by name or category in the database.

    Args:
        query: Product name, partial name, or category (e.g. "Electronics").

    Returns:
        A list of matching products with price and stock, or a not-found message.
    """
    conn = _get_connection()
    cursor = conn.cursor(dictionary=True)
    like_query = f"%{query}%"
    cursor.execute(
        "SELECT product_name, category, price, stock FROM products "
        "WHERE product_name LIKE %s OR category LIKE %s",
        (like_query, like_query),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return f"No products found matching '{query}'."

    lines = [
        f"- {r['product_name']} ({r['category']}): Rs. {r['price']:,.2f}, "
        f"{r['stock']} units in stock"
        for r in rows
    ]
    return "\n".join(lines)


@mcp.tool()
def get_user_address(user_name: str) -> str:
    """
    Get the home address of a specific named customer from the customer
    database.

    IMPORTANT: This tool requires a specific person's name. If the question
    refers to a user without naming them, do NOT call this tool — ask the
    user directly which person they mean and wait for their reply.

    IMPORTANT: More than one customer may share a similar name. If this
    tool reports that multiple customers match, do NOT guess. Relay the
    list back to the user, ask which one they mean, and wait for their reply.

    Args:
        user_name: The exact or approximate name of the customer.

    Returns:
        The customer's address if exactly one match is found; a message
        listing all matching names if more than one matches; or a
        not-found message if no matching user exists.
    """
    conn = _get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name, address FROM users WHERE name LIKE %s", (f"%{user_name}%",))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return f"No user found matching '{user_name}'."
    if len(rows) > 1:
        matching_names = ", ".join(r["name"] for r in rows)
        return (
            f"Multiple customers match '{user_name}': {matching_names}. "
            f"Please ask the user which specific person they mean before proceeding."
        )
    row = rows[0]
    return f"{row['name']}'s address: {row['address']}"


def _find_unique_customer(cursor, name: str):
    """Returns (row_or_None, ambiguity_message_or_None)."""
    cursor.execute("SELECT id, name FROM users WHERE name LIKE %s", (f"%{name}%",))
    rows = cursor.fetchall()
    if not rows:
        return None, f"No customer found matching '{name}'."
    if len(rows) > 1:
        names = ", ".join(r["name"] for r in rows)
        return None, f"Multiple customers match '{name}': {names}. Please ask which one is meant."
    return rows[0], None


def _find_unique_product(cursor, name: str):
    """Returns (row_or_None, ambiguity_message_or_None)."""
    cursor.execute("SELECT id, product_name FROM products WHERE product_name LIKE %s", (f"%{name}%",))
    rows = cursor.fetchall()
    if not rows:
        return None, f"No product found matching '{name}'."
    if len(rows) > 1:
        names = ", ".join(r["product_name"] for r in rows)
        return None, f"Multiple products match '{name}': {names}. Please ask which one is meant."
    return rows[0], None


@mcp.tool()
def schedule_delivery(customer_name: str, product_name: str, delivery_date: str) -> str:
    """
    Schedule a product delivery for a specific customer on a specific date.

    Use this ONLY when the user explicitly wants to schedule, book, or
    arrange a delivery. This is a THREE-parameter tool — customer_name,
    product_name, and delivery_date are ALL required, with no defaults.

    IMPORTANT: If the question is missing one, two, or all three of these
    pieces of information, do NOT call this tool. Instead, ask the user for
    whichever piece(s) are missing — you may ask for several at once in a
    single question — and wait for their reply before calling this tool.

    IMPORTANT: Even when all three pieces of information are supplied, the
    customer name or product name individually might match more than one
    record. If this tool reports an ambiguous match for either, do NOT
    guess — relay the ambiguity to the user as a question and wait for a
    more specific reply before calling this tool again.

    Args:
        customer_name: The customer's name, e.g. "John Perera".
        product_name: The product being delivered, e.g. "Laptop A".
        delivery_date: The requested delivery date, in YYYY-MM-DD format.

    Returns:
        A confirmation message if scheduled successfully; an ambiguity
        message naming the specific field that needs clarification; or a
        not-found message if the customer or product doesn't exist.
    """
    conn = _get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deliveries (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            product_name VARCHAR(255) NOT NULL,
            delivery_date VARCHAR(20) NOT NULL
        )
    """)

    customer, customer_error = _find_unique_customer(cursor, customer_name)
    if customer_error:
        cursor.close()
        conn.close()
        return f"Cannot schedule delivery — customer field needs clarification: {customer_error}"

    product, product_error = _find_unique_product(cursor, product_name)
    if product_error:
        cursor.close()
        conn.close()
        return f"Cannot schedule delivery — product field needs clarification: {product_error}"

    cursor.execute(
        "INSERT INTO deliveries (customer_name, product_name, delivery_date) VALUES (%s, %s, %s)",
        (customer["name"], product["product_name"], delivery_date),
    )
    conn.commit()
    cursor.close()
    conn.close()

    return (
        f"Delivery scheduled: {product['product_name']} for {customer['name']} "
        f"on {delivery_date}."
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")