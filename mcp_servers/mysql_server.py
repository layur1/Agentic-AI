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


def _ensure_deliveries_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS deliveries (
            id INT AUTO_INCREMENT PRIMARY KEY,
            customer_name VARCHAR(255) NOT NULL,
            product_name VARCHAR(255) NOT NULL,
            delivery_date VARCHAR(20) NOT NULL
        )
    """)


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


# =====================================================================
# Product tools
# =====================================================================

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

    Use this for general product lookups, browsing by category, or when
    the user names a category rather than a specific product. Do NOT use
    this for a specific numeric price range — use
    get_products_by_price_range for that instead.

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
def get_products_by_price_range(min_price: float, max_price: float) -> str:
    """
    Find products whose price falls within a specific numeric range.

    Use this ONLY for questions naming a price range or budget (for
    example, "what do you have between Rs. 5,000 and Rs. 20,000" or
    "anything under Rs. 200,000"). Do NOT use this for a single named
    product's price — use get_price for that instead.

    IMPORTANT: Both min_price and max_price are required, with no
    defaults. If the question implies an open-ended range (e.g. "under
    Rs. 200,000" has an implicit minimum), you may use 0 as the minimum
    in that specific case — but if the range is genuinely ambiguous, ask
    the user to clarify rather than guessing bounds.

    Args:
        min_price: The lower bound of the price range, in Rupees.
        max_price: The upper bound of the price range, in Rupees.

    Returns:
        A list of matching products, or a message if none fall in range.
    """
    conn = _get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT product_name, category, price, stock FROM products "
        "WHERE price BETWEEN %s AND %s ORDER BY price ASC",
        (min_price, max_price),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return f"No products found between Rs. {min_price:,.2f} and Rs. {max_price:,.2f}."

    lines = [
        f"- {r['product_name']} ({r['category']}): Rs. {r['price']:,.2f}, "
        f"{r['stock']} units in stock"
        for r in rows
    ]
    return f"Products between Rs. {min_price:,.2f} and Rs. {max_price:,.2f}:\n" + "\n".join(lines)


# =====================================================================
# Customer tools
# =====================================================================

@mcp.tool()
def get_user_address(user_name: str) -> str:
    """
    Get the home address of a specific named customer from the customer
    database.

    Use this ONLY when the goal is specifically to retrieve someone's
    address. Do NOT use this just to check whether a customer exists or
    to browse/search customer names — use search_customers for that.

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
            f"Please ask the user which specific person they mean "
            f"(ideally by full name) before looking up an address."
        )

    row = rows[0]
    return f"{row['name']}'s address: {row['address']}"


@mcp.tool()
def search_customers(query: str) -> str:
    """
    Search/browse customer records by partial name, WITHOUT revealing
    their address.

    Use this when the user wants to find out who is in the customer
    database, check whether a customer exists, or see a list of similar
    names — for example "do we have any customers named John" or "how
    many customers are named Fernando". Do NOT use this if the actual
    goal is to retrieve a specific person's address — use
    get_user_address for that instead, since this tool deliberately does
    not return address details.

    Args:
        query: Full or partial customer name to search for.

    Returns:
        A list of matching customer names (no addresses), or a not-found message.
    """
    conn = _get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT name FROM users WHERE name LIKE %s", (f"%{query}%",))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return f"No customers found matching '{query}'."
    names = "\n".join(f"- {r['name']}" for r in rows)
    return f"{len(rows)} customer(s) match '{query}':\n{names}"


@mcp.tool()
def add_new_customer(name: str, address: str) -> str:
    """
    Register a new customer in the database.

    Use this ONLY when the user explicitly wants to add, register, or
    create a new customer record. This is a TWO-parameter tool — both
    name and address are required, with no defaults.

    IMPORTANT: If either the name or the address is missing from the
    request, do NOT call this tool. Ask the user for whichever piece is
    missing (both at once if both are missing) and wait for their reply.

    Note: this tool does not check for existing customers with the same
    or a similar name before adding — duplicate or similar names are
    allowed, since real customers can genuinely share a name. If the user
    seems concerned about creating a duplicate, you may first use
    search_customers to check before calling this tool.

    Args:
        name: The new customer's full name.
        address: The new customer's address.

    Returns:
        A confirmation message.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (name, address) VALUES (%s, %s)", (name, address))
    conn.commit()
    cursor.close()
    conn.close()
    return f"New customer added: {name}, {address}."


# =====================================================================
# Delivery tools
# =====================================================================

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
    guess — relay the ambiguity to the user and wait for a more specific
    reply before calling this tool again.

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
    _ensure_deliveries_table(cursor)

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


@mcp.tool()
def get_delivery_status(customer_name: str) -> str:
    """
    List all scheduled deliveries for a specific customer.

    Use this for questions like "what deliveries does X have scheduled"
    or "when is X's delivery arriving". Do NOT use this to schedule a NEW
    delivery — use schedule_delivery for that.

    IMPORTANT: This tool requires a customer name. If the question doesn't
    name a specific customer, do not call this tool — ask who they mean.

    IMPORTANT: If the name matches more than one customer, do not guess —
    relay the ambiguity to the user and wait for a more specific name.

    Args:
        customer_name: The customer's name, e.g. "John Perera".

    Returns:
        A list of that customer's scheduled deliveries, an ambiguity
        message, or a message if they have none scheduled.
    """
    conn = _get_connection()
    cursor = conn.cursor(dictionary=True)
    _ensure_deliveries_table(cursor)

    customer, customer_error = _find_unique_customer(cursor, customer_name)
    if customer_error:
        cursor.close()
        conn.close()
        return f"Cannot check delivery status — needs clarification: {customer_error}"

    cursor.execute(
        "SELECT product_name, delivery_date FROM deliveries WHERE customer_name = %s",
        (customer["name"],),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    if not rows:
        return f"{customer['name']} has no deliveries currently scheduled."
    lines = "\n".join(f"- {r['product_name']} on {r['delivery_date']}" for r in rows)
    return f"Scheduled deliveries for {customer['name']}:\n{lines}"


@mcp.tool()
def cancel_delivery(customer_name: str, product_name: str) -> str:
    """
    Cancel a previously scheduled delivery for a customer.

    Use this ONLY when the user explicitly wants to cancel, stop, or
    remove an existing scheduled delivery. This is a TWO-parameter tool —
    both customer_name and product_name are required.

    IMPORTANT: If either piece of information is missing, do NOT call
    this tool. Ask the user for whichever piece is missing and wait for
    their reply.

    IMPORTANT: If the customer name or product name matches more than one
    record, do not guess — relay the ambiguity to the user and wait for a
    more specific reply.

    Args:
        customer_name: The customer's name whose delivery should be cancelled.
        product_name: The product whose delivery should be cancelled.

    Returns:
        A confirmation message if a matching delivery was cancelled; an
        ambiguity message; or a message if no matching delivery was found.
    """
    conn = _get_connection()
    cursor = conn.cursor(dictionary=True)
    _ensure_deliveries_table(cursor)

    customer, customer_error = _find_unique_customer(cursor, customer_name)
    if customer_error:
        cursor.close()
        conn.close()
        return f"Cannot cancel delivery — customer field needs clarification: {customer_error}"

    product, product_error = _find_unique_product(cursor, product_name)
    if product_error:
        cursor.close()
        conn.close()
        return f"Cannot cancel delivery — product field needs clarification: {product_error}"

    cursor.execute(
        "SELECT id FROM deliveries WHERE customer_name = %s AND product_name = %s",
        (customer["name"], product["product_name"]),
    )
    match = cursor.fetchone()
    if not match:
        cursor.close()
        conn.close()
        return f"No scheduled delivery found for {customer['name']} — {product['product_name']}."

    cursor.execute("DELETE FROM deliveries WHERE id = %s", (match["id"],))
    conn.commit()
    cursor.close()
    conn.close()
    return f"Cancelled the delivery of {product['product_name']} for {customer['name']}."


if __name__ == "__main__":
    mcp.run(transport="stdio")