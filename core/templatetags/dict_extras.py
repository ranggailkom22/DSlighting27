from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Custom template filter to get item from dictionary using a key
    Usage: {{ my_dict|get_item:key }}
    """
    try:
        return dictionary.get(key)
    except:
        return None