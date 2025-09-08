from django import template
from decimal import Decimal, InvalidOperation
import re

register = template.Library()

@register.filter
def dedupe_qty(value):
    """Remove repeated quantity/unit groups regardless of numeric formatting.
    Examples:
        'Item (1 Each) (1.00 Each)' -> 'Item (1 Each)'
        'Fill (6.5 Yards) (6.50 Yards)' -> 'Fill (6.5 Yards)'
    """
    if not isinstance(value, str):
        return value

    pattern = r"\((\d+(?:\.\d+)?)\s*([^()]+?)\)"
    seen = set()

    def repl(match):
        qty_str, unit = match.groups()
        unit = unit.strip()
        try:
            qty_val = Decimal(qty_str).normalize()
        except (InvalidOperation, ValueError):
            key = (qty_str, unit.lower())
        else:
            key = (qty_val, unit.lower())
        if key in seen:
            return ""
        seen.add(key)
        return match.group(0)

    result = re.sub(pattern, repl, value)
    # Collapse multiple spaces left by removals
    return re.sub(r"\s{2,}", " ", result).strip()
