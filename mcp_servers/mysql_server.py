import os
import sys
from contextlib import contextmanager
from datetime import datetime


sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)


from mcp.server.fastmcp import FastMCP
import mysql.connector

import config
import cache


mcp = FastMCP("mysql-server")


# ============================================================
# DATABASE CONNECTION
# ============================================================

def _get_connection():

    return mysql.connector.connect(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
    )


@contextmanager
def _db_cursor():
    """
    Safely manage a MySQL connection and cursor.
    """

    connection = _get_connection()
    cursor = None

    try:

        cursor = connection.cursor()

        yield connection, cursor

    finally:

        if cursor is not None:
            cursor.close()

        connection.close()


# ============================================================
# DELIVERY TABLE
# ============================================================

def _ensure_deliveries_table():

    with _db_cursor() as (
        connection,
        cursor
    ):

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS deliveries (
                id INT AUTO_INCREMENT PRIMARY KEY,
                customer_name VARCHAR(255) NOT NULL,
                product_name VARCHAR(255) NOT NULL,
                delivery_date DATE NOT NULL
            )
            """
        )

        connection.commit()


# ============================================================
# CUSTOMER LOOKUP
# ============================================================

def _find_unique_customer(
    cursor,
    customer_name
):

    cursor.execute(
        """
        SELECT id, name, address
        FROM users
        WHERE name LIKE %s
        """,
        (
            f"%{customer_name}%",
        ),
    )

    rows = cursor.fetchall()

    if len(rows) == 0:

        return None, "No customer was found."

    if len(rows) > 1:

        names = [
            row[1]
            for row in rows
        ]

        return None, (
            "Multiple customers matched: "
            + ", ".join(names)
            + ". Please specify the customer."
        )

    return rows[0], None


# ============================================================
# PRODUCT LOOKUP
# ============================================================

def _find_unique_product(
    cursor,
    product_name
):

    cursor.execute(
        """
        SELECT id, product_name, price, stock, category
        FROM products
        WHERE product_name LIKE %s
        """,
        (
            f"%{product_name}%",
        ),
    )

    rows = cursor.fetchall()

    if len(rows) == 0:

        return None, "No product was found."

    if len(rows) > 1:

        names = [
            row[1]
            for row in rows
        ]

        return None, (
            "Multiple products matched: "
            + ", ".join(names)
            + ". Please specify the product."
        )

    return rows[0], None


# ============================================================
# DELIVERY DATE VALIDATION
# ============================================================

def _validate_delivery_date(value):

    if not value or not value.strip():
        return None

    try:

        return datetime.strptime(
            value.strip(),
            "%Y-%m-%d"
        ).date()

    except ValueError:

        return None


# ============================================================
# PRODUCT TOOLS
# ============================================================

@mcp.tool(
    name="get_price",
    description=(
        "Get the current price of one specific product from the "
        "live product database. Use this when the user asks how "
        "much a specific product currently costs."
    ),
)
def get_price(product_name: str) -> str:

    if not product_name or not product_name.strip():
        return "A product name is required."

    normalized_name = product_name.strip()
    cached_result = cache.get("get_price", normalized_name)
    if cached_result is not None:
        return cached_result

    with _db_cursor() as (
        connection,
        cursor
    ):

        product, error = _find_unique_product(
            cursor,
            normalized_name
        )

        if error:
            return error

        result = (
            f"{product[1]} currently costs "
            f"{float(product[2]):,.2f}."
        )
        cache.set("get_price", result, normalized_name)
        return result


@mcp.tool(
    name="check_stock",
    description=(
        "Check the current inventory quantity of one specific "
        "product. Use this when the user asks whether a product "
        "is in stock or how many units are available."
    ),
)
def check_stock(product_name: str) -> str:

    if not product_name or not product_name.strip():
        return "A product name is required."

    normalized_name = product_name.strip()
    cached_result = cache.get("check_stock", normalized_name)
    if cached_result is not None:
        return cached_result

    with _db_cursor() as (
        connection,
        cursor
    ):

        product, error = _find_unique_product(
            cursor,
            normalized_name
        )

        if error:
            return error

        stock = int(product[3])

        if stock > 0:

            result = (
                f"{product[1]} is currently in stock. "
                f"Available quantity: {stock}."
            )
        else:
            result = (
                f"{product[1]} is currently out of stock."
            )

        cache.set("check_stock", result, normalized_name)
        return result


@mcp.tool(
    name="search_products",
    description=(
        "Search the live product catalog using a product name "
        "or category. Use this when the user wants to browse "
        "or find products rather than retrieve one exact product."
    ),
)
def search_products(query: str) -> str:

    if not query or not query.strip():
        return "A search query is required."

    normalized_query = query.strip()
    cached_result = cache.get("search_products", normalized_query)
    if cached_result is not None:
        return cached_result

    with _db_cursor() as (
        connection,
        cursor
    ):

        search_value = f"%{normalized_query}%"

        cursor.execute(
            """
            SELECT product_name, category, price, stock
            FROM products
            WHERE product_name LIKE %s
               OR category LIKE %s
            ORDER BY product_name
            """,
            (
                search_value,
                search_value,
            ),
        )

        rows = cursor.fetchall()

        if not rows:
            return "No matching products were found."

        results = []

        for row in rows:

            results.append(
                f"{row[0]} | "
                f"Category: {row[1]} | "
                f"Price: {float(row[2]):,.2f} | "
                f"Stock: {row[3]}"
            )

        result = "\n".join(results)
        cache.set("search_products", result, normalized_query)
        return result


@mcp.tool(
    name="get_products_by_price_range",
    description=(
        "Find products whose current price falls between a "
        "minimum and maximum price. Use this when the user asks "
        "for products within a numeric price range."
    ),
)
def get_products_by_price_range(
    min_price: float,
    max_price: float,
) -> str:

    if min_price < 0 or max_price < 0:

        return "Prices cannot be negative."

    if min_price > max_price:

        return (
            "The minimum price cannot be greater than "
            "the maximum price."
        )

    cached_result = cache.get(
        "get_products_by_price_range",
        min_price,
        max_price,
    )
    if cached_result is not None:
        return cached_result

    with _db_cursor() as (
        connection,
        cursor
    ):

        cursor.execute(
            """
            SELECT product_name, category, price, stock
            FROM products
            WHERE price BETWEEN %s AND %s
            ORDER BY price
            """,
            (
                min_price,
                max_price,
            ),
        )

        rows = cursor.fetchall()

        if not rows:

            result = (
                f"No products were found between "
                f"{min_price:,.2f} and "
                f"{max_price:,.2f}."
            )
            cache.set("get_products_by_price_range", result, min_price, max_price)
            return result

        results = []

        for row in rows:

            results.append(
                f"{row[0]} | "
                f"Category: {row[1]} | "
                f"Price: {float(row[2]):,.2f} | "
                f"Stock: {row[3]}"
            )

        result = "\n".join(results)
        cache.set("get_products_by_price_range", result, min_price, max_price)
        return result


# ============================================================
# CUSTOMER TOOLS
# ============================================================

@mcp.tool(
    name="get_user_address",
    description=(
        "Retrieve the address of one specific customer. "
        "Use this when the user asks for the stored address "
        "of a named customer."
    ),
)
def get_user_address(user_name: str) -> str:

    if not user_name or not user_name.strip():
        return "A customer name is required."

    normalized_name = user_name.strip()
    cached_result = cache.get("get_user_address", normalized_name)
    if cached_result is not None:
        return cached_result

    with _db_cursor() as (
        connection,
        cursor
    ):

        customer, error = _find_unique_customer(
            cursor,
            normalized_name
        )

        if error:
            return error

        result = (
            f"{customer[1]}'s address is: "
            f"{customer[2]}"
        )
        cache.set("get_user_address", result, normalized_name)
        return result


@mcp.tool(
    name="search_customers",
    description=(
        "Search the customer database by customer name. "
        "Returns matching customer names without revealing "
        "their addresses."
    ),
)
def search_customers(query: str) -> str:

    if not query or not query.strip():
        return "A customer search query is required."

    normalized_query = query.strip()
    cached_result = cache.get("search_customers", normalized_query)
    if cached_result is not None:
        return cached_result

    with _db_cursor() as (
        connection,
        cursor
    ):

        search_value = f"%{normalized_query}%"

        cursor.execute(
            """
            SELECT name
            FROM users
            WHERE name LIKE %s
            ORDER BY name
            """,
            (search_value,),
        )

        rows = cursor.fetchall()

        if not rows:
            return "No matching customers were found."

        result = "\n".join(
            row[0]
            for row in rows
        )
        cache.set("search_customers", result, normalized_query)
        return result


@mcp.tool(
    name="add_new_customer",
    description=(
        "Register a new customer in the customer database "
        "using the customer's name and address."
    ),
)
def add_new_customer(
    name: str,
    address: str,
) -> str:

    if not name or not name.strip():
        return "Customer name is required."

    if not address or not address.strip():
        return "Customer address is required."

    with _db_cursor() as (
        connection,
        cursor
    ):

        cursor.execute(
            """
            INSERT INTO users (name, address)
            VALUES (%s, %s)
            """,
            (
                name.strip(),
                address.strip(),
            ),
        )

        connection.commit()

    cache.invalidate_tool("search_customers")
    cache.invalidate_tool("get_user_address")
    return (
        f"Customer '{name.strip()}' "
        "was successfully added."
    )


# ============================================================
# DELIVERY TOOLS
# ============================================================

@mcp.tool(
    name="schedule_delivery",
    description=(
        "Schedule a product delivery for a customer. "
        "Requires a customer name, product name, and delivery "
        "date in YYYY-MM-DD format."
    ),
)
def schedule_delivery(
    customer_name: str,
    product_name: str,
    delivery_date: str,
) -> str:

    if not customer_name or not customer_name.strip():

        return "Customer name is required."

    if not product_name or not product_name.strip():

        return "Product name is required."

    if not delivery_date or not delivery_date.strip():

        return "Delivery date is required."

    date_value = _validate_delivery_date(
        delivery_date
    )

    if date_value is None:

        return (
            "Invalid delivery date. "
            "Please provide the date in YYYY-MM-DD format."
        )

    _ensure_deliveries_table()

    with _db_cursor() as (
        connection,
        cursor
    ):

        customer, customer_error = _find_unique_customer(
            cursor,
            customer_name.strip()
        )

        if customer_error:
            return customer_error

        product, product_error = _find_unique_product(
            cursor,
            product_name.strip()
        )

        if product_error:
            return product_error

        cursor.execute(
            """
            INSERT INTO deliveries
            (customer_name, product_name, delivery_date)
            VALUES (%s, %s, %s)
            """,
            (
                customer[1],
                product[1],
                date_value,
            ),
        )

        connection.commit()

    cache.invalidate_tool("get_delivery_status")
    return (
        f"Delivery scheduled for {customer[1]}: "
        f"{product[1]} on {date_value}."
    )


@mcp.tool(
    name="get_delivery_status",
    description=(
        "Retrieve scheduled deliveries for a specific customer. "
        "Use this when the user asks about a customer's delivery "
        "schedule or delivery status."
    ),
)
def get_delivery_status(customer_name: str) -> str:

    if not customer_name or not customer_name.strip():

        return "Customer name is required."

    normalized_name = customer_name.strip()
    cached_result = cache.get("get_delivery_status", normalized_name)
    if cached_result is not None:
        return cached_result

    _ensure_deliveries_table()

    with _db_cursor() as (
        connection,
        cursor
    ):

        customer, error = _find_unique_customer(
            cursor,
            normalized_name
        )

        if error:
            return error

        cursor.execute(
            """
            SELECT product_name, delivery_date
            FROM deliveries
            WHERE customer_name = %s
            ORDER BY delivery_date
            """,
            (customer[1],),
        )

        rows = cursor.fetchall()

        if not rows:

            result = (
                f"No scheduled deliveries were found "
                f"for {customer[1]}."
            )
            cache.set("get_delivery_status", result, normalized_name)
            return result

        results = [
            f"{row[0]} — {row[1]}"
            for row in rows
        ]

        result = (
            f"Scheduled deliveries for {customer[1]}:\n"
            + "\n".join(results)
        )
        cache.set("get_delivery_status", result, normalized_name)
        return result


@mcp.tool(
    name="cancel_delivery",
    description=(
        "Cancel a scheduled delivery for a customer and product. "
        "Requires the customer name and product name. If multiple "
        "matching deliveries exist, the user must clarify which "
        "delivery should be cancelled."
    ),
)
def cancel_delivery(
    customer_name: str,
    product_name: str,
) -> str:

    if not customer_name or not customer_name.strip():

        return "Customer name is required."

    if not product_name or not product_name.strip():

        return "Product name is required."

    _ensure_deliveries_table()

    with _db_cursor() as (
        connection,
        cursor
    ):

        customer, customer_error = _find_unique_customer(
            cursor,
            customer_name.strip()
        )

        if customer_error:
            return customer_error

        product, product_error = _find_unique_product(
            cursor,
            product_name.strip()
        )

        if product_error:
            return product_error

        cursor.execute(
            """
            SELECT id, delivery_date
            FROM deliveries
            WHERE customer_name = %s
              AND product_name = %s
            ORDER BY delivery_date
            """,
            (
                customer[1],
                product[1],
            ),
        )

        rows = cursor.fetchall()

        if not rows:

            return (
                f"No scheduled delivery was found for "
                f"{customer[1]} and {product[1]}."
            )

        if len(rows) > 1:

            dates = ", ".join(
                str(row[1])
                for row in rows
            )

            return (
                "Multiple deliveries were found for this "
                f"customer and product: {dates}. "
                "Please specify which delivery should be cancelled."
            )

        delivery_id = rows[0][0]

        cursor.execute(
            """
            DELETE FROM deliveries
            WHERE id = %s
            """,
            (delivery_id,),
        )

        connection.commit()

    cache.invalidate_tool("get_delivery_status")
    return (
        f"The delivery of {product[1]} for "
        f"{customer[1]} was cancelled."
    )


# ============================================================
# SERVER START
# ============================================================

if __name__ == "__main__":
    mcp.run(transport="stdio")