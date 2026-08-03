"""
FastMCP server exposing MySQL product data as tools.

Exposes three tools: get_price, check_stock, search_products.

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


if __name__ == "__main__":
    mcp.run(transport="stdio")