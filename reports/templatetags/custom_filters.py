from django import template

register = template.Library()

@register.filter
def currency(value, symbol="$"):
    """
    Format a number as currency.
    Usage: {{ value|currency }} or {{ value|currency:"€" }}
    """
    try:
        value = float(value)
    except (ValueError, TypeError):
        return value
    return f"{symbol}{value:,.2f}"

@register.filter
def negative_currency(value, symbol="$"):
    """
    Format a number as currency.
    Usage: {{ value|currency }} or {{ value|currency:"€" }}
    """
    try:
        value = float(value)
        value = value*-1
    except (ValueError, TypeError):
        return value
    return f"{symbol}{value:,.2f}"