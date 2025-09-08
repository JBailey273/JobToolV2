from django import template
import re

register = template.Library()

@register.filter
def dedupe_qty(value):
    """Remove repeated trailing quantity/unit groups.
    Example: 'Item (1 Each) (1 Each)' -> 'Item (1 Each)'"""
    if not isinstance(value, str):
        return value
    pattern = r'(\([^()]+\))(?:\s*\1)+'
    return re.sub(pattern, r'\1', value)
