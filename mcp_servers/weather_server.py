"""
FastMCP server exposing local weather data as tools.

Includes get_weather_alert(city, date) — a genuine TWO-required-parameter
tool, added to demonstrate and test multi-parameter clarification handling.

Run standalone for debugging:
    python mcp_servers/weather_server.py
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather-server")

CURRENT_WEATHER = {
    "colombo": {"temperature_c": 30, "condition": "Partly Cloudy", "humidity": 78},
    "kandy": {"temperature_c": 24, "condition": "Light Rain", "humidity": 85},
    "galle": {"temperature_c": 29, "condition": "Sunny", "humidity": 70},
    "negombo": {"temperature_c": 31, "condition": "Humid", "humidity": 80},
    "jaffna": {"temperature_c": 33, "condition": "Clear Skies", "humidity": 65},
}

FORECAST = {
    "colombo": [
        {"day": "Tomorrow", "condition": "Thunderstorms", "high_c": 31, "low_c": 25},
        {"day": "Day 2", "condition": "Partly Cloudy", "high_c": 30, "low_c": 24},
        {"day": "Day 3", "condition": "Sunny", "high_c": 32, "low_c": 25},
    ],
    "kandy": [
        {"day": "Tomorrow", "condition": "Light Rain", "high_c": 25, "low_c": 19},
        {"day": "Day 2", "condition": "Overcast", "high_c": 24, "low_c": 18},
        {"day": "Day 3", "condition": "Light Rain", "high_c": 23, "low_c": 18},
    ],
    "galle": [
        {"day": "Tomorrow", "condition": "Sunny", "high_c": 30, "low_c": 26},
        {"day": "Day 2", "condition": "Sunny", "high_c": 30, "low_c": 26},
        {"day": "Day 3", "condition": "Partly Cloudy", "high_c": 29, "low_c": 25},
    ],
    "negombo": [
        {"day": "Tomorrow", "condition": "Humid, Scattered Showers", "high_c": 31, "low_c": 26},
        {"day": "Day 2", "condition": "Humid", "high_c": 32, "low_c": 26},
        {"day": "Day 3", "condition": "Partly Cloudy", "high_c": 31, "low_c": 25},
    ],
    "jaffna": [
        {"day": "Tomorrow", "condition": "Clear Skies", "high_c": 34, "low_c": 26},
        {"day": "Day 2", "condition": "Sunny", "high_c": 33, "low_c": 26},
        {"day": "Day 3", "condition": "Clear Skies", "high_c": 33, "low_c": 25},
    ],
}

# Dummy severe-weather alert data, keyed by (city, date).
SEVERE_ALERTS = {
    ("colombo", "2026-08-25"): "Heavy thunderstorm warning in effect, 2 PM - 8 PM.",
    ("negombo", "2026-08-26"): "Coastal flooding advisory due to high tide and rain.",
}


@mcp.tool()
def get_current_weather(city: str) -> str:
    """
    Get the current weather conditions for a Sri Lankan city.

    Use this for questions about today's or right-now weather. Do NOT use
    this for future forecasts or alerts, and do NOT use this for anything
    unrelated to weather.

    IMPORTANT: This tool requires a city. If the question doesn't name one,
    do not call this tool — ask the user which city they mean and wait for
    their reply.

    Args:
        city: The city name, e.g. "Colombo", "Kandy", "Galle".

    Returns:
        Current temperature, condition, and humidity, or a not-found message.
    """
    key = city.strip().lower()
    data = CURRENT_WEATHER.get(key)
    if not data:
        available = ", ".join(c.title() for c in CURRENT_WEATHER)
        return f"No current weather data for '{city}'. Available cities: {available}."
    return (
        f"Current weather in {city.title()}: {data['condition']}, "
        f"{data['temperature_c']}°C, {data['humidity']}% humidity."
    )


@mcp.tool()
def get_weather_forecast(city: str, days: int = 3) -> str:
    """
    Get the upcoming multi-day weather forecast for a Sri Lankan city.

    Use this for questions about future weather. Do NOT use this for
    current/right-now conditions (use get_current_weather instead).

    IMPORTANT: This tool requires a city. If the question doesn't name one,
    do not call this tool — ask the user which city they mean and wait for
    their reply. 'days' is optional and defaults to 3 if not specified.

    Args:
        city: The city name, e.g. "Colombo", "Kandy", "Galle".
        days: How many days of forecast to return (1-3). Defaults to 3.

    Returns:
        A day-by-day forecast, or a not-found message.
    """
    key = city.strip().lower()
    forecast = FORECAST.get(key)
    if not forecast:
        available = ", ".join(c.title() for c in FORECAST)
        return f"No forecast data for '{city}'. Available cities: {available}."

    days = max(1, min(days, len(forecast)))
    lines = [
        f"{entry['day']}: {entry['condition']}, high {entry['high_c']}°C / low {entry['low_c']}°C"
        for entry in forecast[:days]
    ]
    return f"Forecast for {city.title()}:\n" + "\n".join(lines)


@mcp.tool()
def get_weather_alert(city: str, date: str) -> str:
    """
    Check for severe weather alerts (storm warnings, flood advisories, etc.)
    for a specific city on a specific date.

    Use this ONLY when the question asks about weather alerts, warnings, or
    advisories for a particular date. Do NOT use this for ordinary current
    conditions or forecasts — use get_current_weather or get_weather_forecast
    for those instead.

    IMPORTANT: This tool requires BOTH a city AND a date. Both are required
    — there is no default for either. If the question is missing one or
    both of these, do NOT call this tool. Instead, ask the user for
    whichever piece (or pieces) are missing — you may ask for both in a
    single question if both are absent — and wait for their reply before
    calling this tool.

    Args:
        city: The city name, e.g. "Colombo", "Negombo".
        date: The date to check, in YYYY-MM-DD format, e.g. "2026-08-25".

    Returns:
        A description of any active alert, or a message confirming there
        are no alerts for that city and date.
    """
    key = (city.strip().lower(), date.strip())
    alert = SEVERE_ALERTS.get(key)
    if alert:
        return f"ALERT for {city.title()} on {date}: {alert}"
    return f"No severe weather alerts for {city.title()} on {date}."


if __name__ == "__main__":
    mcp.run(transport="stdio")