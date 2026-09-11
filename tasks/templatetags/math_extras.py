from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply the arg and the value"""
    return value * int(arg)

@register.inclusion_tag('accounts/navbar.html')
def open_tasks():
    return 8