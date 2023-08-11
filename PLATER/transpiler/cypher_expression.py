"""Encode Python JSON-able objects as Cypher expressions."""


def encode_dict(obj):
    """Encode dictionary."""
    return "{" + ", ".join(
        key + ": " + dumps(value)
        for key, value in obj.items()
    ) + "}"


def encode_list(obj):
    """Encode list."""
    return "[" + ", ".join(
        dumps(el) for el in obj
    ) + "]"


def encode_str(obj):
    """Encode string."""
    return f"\"{obj}\""


def encode_none(obj):
    """Encode None."""
    return "null"


def encode_bool(obj):
    """Encode boolean."""
    return "true" if obj else "false"


def dumps(obj):
    """Convert Python obj to Cypher expression."""
    if isinstance(obj, dict):
        return encode_dict(obj)
    elif isinstance(obj, list):
        return encode_list(obj)
    elif isinstance(obj, str):
        return encode_str(obj)
    elif isinstance(obj, bool):
        return encode_bool(obj)
    elif obj is None:
        return encode_none(obj)
    else:
        return str(obj)
