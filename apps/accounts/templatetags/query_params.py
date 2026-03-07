from django import template

register = template.Library()


@register.filter
def query_get(request, key):
    try:
        return request.GET.get(key, "")
    except Exception:
        return ""
