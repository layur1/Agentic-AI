"""
FastMCP server exposing MySQL product and user data as tools.

Exposes four tools: get_price, check_stock, search_products, get_user_address.

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

    Use this for questions like "is X in stock" or "how many units of X
    are left" — this is live database data, not PDF documentation.

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

    Use this for general product lookups, browsing by category, or when
    the user names a category rather than a specific product.

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
    refers to a user without naming them — for example "his address",
    "her address", "their address", or "the customer's address" — do NOT
    call this tool and do NOT guess or invent a name. Instead, respond by
    asking the user directly which person's name they mean, and wait for
    their answer in a future message before calling this tool.

    IMPORTANT: More than one customer may share the same or a similar name
    (for example, two customers both named "John"). If this tool reports
    that multiple customers match, do NOT guess or arbitrarily pick one of
    them. Instead, relay the list of matching names back to the user exactly
    as returned, ask them which specific person they mean, and wait for
    their reply — ideally the person's full name — before calling this tool
    again.

    Args:
        user_name: The exact or approximate name of the customer,
            e.g. "John Perera". Must be an actual name mentioned in the
            conversation, never a placeholder or guess.

    Returns:
        The customer's address if exactly one match is found; a message
        listing all matching names if more than one customer matches; or a
        not-found message if no matching user exists.
    """
    conn = _get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT name, address FROM users WHERE name LIKE %s",
        (f"%{user_name}%",),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return f"No user found matching '{user_name}'."

    if len(rows) > 1:
        matching_names = ", ".join(r["name"] for r in rows)
        return (
            f"Multiple customers match '{user_name}': {matching_names}. "
            f"Please ask the user which specific person they mean "
            f"(ideally by full name) before looking up an address."
        )

    row = rows[0]
    return f"{row['name']}'s address: {row['address']}"


if __name__ == "__main__":
    mcp.run(transport="stdio")