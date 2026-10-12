import hashlib
import json
import time
from collections import defaultdict

CACHE = {}
TOOL_KEY_INDEX = defaultdict(list)

DEFAULT_TTL_SECONDS = {
    "get_price": 300,
    "check_stock": 180,
    "search_products": 300,
    "get_products_by_price_range": 300,
    "get_user_address": 300,
    "search_customers": 300,
    "get_delivery_status": 300,
    "search_pdf": 600,
}

MUTATING_TOOLS = {
    "add_new_customer",
    "schedule_delivery",
    "cancel_delivery",
}


def _cache_key(tool_name, *args, **kwargs):
    payload = {
        "tool": tool_name,
        "args": args,
        "kwargs": kwargs,
    }
    digest = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(digest.encode("utf-8")).hexdigest()


def is_cacheable(tool_name):
    return tool_name in DEFAULT_TTL_SECONDS and tool_name not in MUTATING_TOOLS


def get(tool_name, *args, **kwargs):
    if not is_cacheable(tool_name):
        return None

    key = _cache_key(tool_name, *args, **kwargs)
    entry = CACHE.get(key)

    if entry is None:
        return None

    if time.time() > entry["expires_at"]:
        CACHE.pop(key, None)
        TOOL_KEY_INDEX.get(tool_name, []).remove(key) if key in TOOL_KEY_INDEX.get(tool_name, []) else None
        return None

    return entry["value"]


def set(tool_name, value, *args, **kwargs):
    if not is_cacheable(tool_name):
        return

    key = _cache_key(tool_name, *args, **kwargs)
    expires_at = time.time() + DEFAULT_TTL_SECONDS[tool_name]

    CACHE[key] = {
        "expires_at": expires_at,
        "value": value,
    }

    existing = TOOL_KEY_INDEX.get(tool_name, [])
    if key not in existing:
        existing.append(key)
        TOOL_KEY_INDEX[tool_name] = existing


def invalidate_tool(tool_name):
    for key in list(TOOL_KEY_INDEX.get(tool_name, [])):
        CACHE.pop(key, None)
    TOOL_KEY_INDEX.pop(tool_name, None)


def clear_all():
    CACHE.clear()
    TOOL_KEY_INDEX.clear()
