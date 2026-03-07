from django import template
from apps.accounts.selectors import user_has_role

register = template.Library()


@register.simple_tag
def has_role(user, role_code):
    return user_has_role(user, role_code)