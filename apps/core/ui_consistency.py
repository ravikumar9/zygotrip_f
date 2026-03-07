"""
Global UI Consistency System
Enforces single background/icon scheme across all templates.
"""

import logging
from typing import Dict, List

from django import template
from django.utils.safestring import mark_safe

logger = logging.getLogger('zygotrip')

register = template.Library()

# Global theme configuration
GLOBAL_THEME = {
    'primary_color': 'var(--primary)',
    'secondary_color': 'var(--secondary)',
    'accent_color': 'var(--warning)',
    'success_color': 'var(--success)',
    'warning_color': 'var(--warning)',
    'danger_color': 'var(--danger)',

    'background_color': 'var(--bg-main)',
    'surface_color': 'var(--bg-card)',
    'border_color': 'var(--secondary)',
    'text_primary': 'var(--text-main)',
    'text_secondary': 'var(--secondary)',

    'font_family': '-apple-system,BlinkMacSystemFont,"Segoe UI","Roboto","Oxygen","Ubuntu","Cantarell","Fira Sans","Droid Sans","Helvetica Neue",sans-serif',
    'border_radius': '8px',

    'icon_set': 'globe',  # Primary icon: globe emoji
    'navbar_background': 'var(--primary)',
    'navbar_text': 'var(--bg-card)',
}

# Global template patterns (enforce consistency)
COMPONENT_PATTERNS = {
    'button': {
        'classes': ['btn', 'btn-primary'],
        'padding': 'py-2 px-4',
        'border_radius': 'rounded-lg',
        'font_weight': 'font-medium',
    },
    'card': {
        'classes': ['card', 'bg-white'],
        'padding': 'p-4',
        'border_radius': 'rounded-lg',
        'shadow': 'shadow-md',
        'border': 'border border-gray-200',
    },
    'input': {
        'classes': ['form-control'],
        'padding': 'py-2 px-3',
        'border_radius': 'rounded-lg',
        'border': 'border border-gray-300',
        'font_size': 'text-sm',
    },
    'navbar': {
        'background': GLOBAL_THEME['navbar_background'],
        'text': GLOBAL_THEME['navbar_text'],
        'height': '64px',
        'padding': 'px-6',
    },
}


@register.simple_tag
def global_theme_color(color_name: str) -> str:
    """Get global theme color"""
    return GLOBAL_THEME.get(color_name, 'var(--text-main)')


@register.simple_tag
def global_icon(icon_name: str) -> str:
    """Return global icon (emoji-based)"""
    icons = {
        'globe': '🌐',
        'home': '🏠',
        'search': '🔍',
        'user': '👤',
        'clock': '🕐',
        'location': '📍',
        'phone': '☎️',
        'mail': '✉️',
        'star': '⭐',
        'heart': '❤️',
        'check': '✓',
        'close': '✕',
        'menu': '☰',
        'arrow_right': '→',
        'arrow_left': '←',
        'arrow_down': '↓',
    }
    
    icon = icons.get(icon_name, icon_name)
    return mark_safe(icon)


@register.inclusion_tag('components/button.html')
def global_button(
    label: str,
    url: str = '',
    button_type: str = 'primary',
    size: str = 'md',
    icon: str = '',
    class_name: str = '',
) -> Dict:
    """Render global button component"""
    return {
        'label': label,
        'url': url,
        'button_type': button_type,
        'size': size,
        'icon': icon,
        'class_name': class_name,
        'theme': GLOBAL_THEME,
    }


@register.inclusion_tag('components/card.html')
def global_card(
    title: str = '',
    content: str = '',
    footer: str = '',
    class_name: str = '',
) -> Dict:
    """Render global card component"""
    return {
        'title': title,
        'content': content,
        'footer': footer,
        'class_name': class_name,
        'theme': GLOBAL_THEME,
    }


@register.inclusion_tag('components/navbar.html')
def global_navbar(
    user=None,
    active_tab: str = '',
) -> Dict:
    """Render global navbar"""
    navbar_items = [
        {'label': 'Home', 'url': '/', 'icon': 'home'},
        {'label': 'Hotels', 'url': '/hotels/', 'icon': 'globe'},
        {'label': 'Buses', 'url': '/buses/', 'icon': 'globe'},
        {'label': 'Cabs', 'url': '/cabs/', 'icon': 'globe'},
        {'label': 'Packages', 'url': '/packages/', 'icon': 'globe'},
    ]
    
    return {
        'user': user,
        'navbar_items': navbar_items,
        'active_tab': active_tab,
        'theme': GLOBAL_THEME,
    }


@register.filter
def global_button_classes(button_type: str = 'primary', size: str = 'md') -> str:
    """Generate button classes based on type and size"""
    base_classes = 'font-medium rounded-lg transition-colors duration-200'
    
    # Button type colors
    type_classes = {
        'primary': 'bg-blue-600 text-white hover:bg-blue-700',
        'secondary': 'bg-gray-200 text-gray-800 hover:bg-gray-300',
        'success': 'bg-green-600 text-white hover:bg-green-700',
        'danger': 'bg-red-600 text-white hover:bg-red-700',
        'outline': 'border-2 border-blue-600 text-blue-600 hover:bg-blue-50',
    }
    
    # Size padding
    size_classes = {
        'sm': 'px-3 py-1 text-sm',
        'md': 'px-4 py-2 text-base',
        'lg': 'px-6 py-3 text-lg',
    }
    
    type_style = type_classes.get(button_type, type_classes['primary'])
    size_style = size_classes.get(size, size_classes['md'])
    
    return f"{base_classes} {type_style} {size_style}"


@register.filter
def global_card_classes(card_type: str = 'default') -> str:
    """Generate card classes"""
    base_classes = 'rounded-lg border border-gray-200 bg-white'
    
    type_classes = {
        'default': 'shadow-md',
        'elevated': 'shadow-lg',
        'outlined': 'shadow-none',
        'filled': 'bg-gray-50 shadow-sm',
    }
    
    type_style = type_classes.get(card_type, type_classes['default'])
    return f"{base_classes} {type_style}"


class UIConsistencyValidator:
    """Validate UI consistency across templates"""
    
    def __init__(self):
        self.violations = []
        self.logger = logging.getLogger('zygotrip')
    
    def validate_template(self, template_path: str, content: str) -> bool:
        """Validate single template for consistency"""
        violations = []
        
        # Check 1: No inline styles
        if 'style=' in content and 'style="' in content:
            violations.append(('inline_styles', 'Found inline styles (should use classes)'))
        
        # Check 2: No hardcoded colors
        color_patterns = ['#', 'rgb(', 'background-color', 'color:']
        if any(pattern in content for pattern in color_patterns):
            violations.append(('hardcoded_colors', 'Found hardcoded colors (should use theme)'))
        
        # Check 3: Button consistency
        if '<button' in content and 'btn' not in content:
            violations.append(('button_style', 'Buttons should use global "btn" classes'))
        
        # Check 4: Icon consistency
        if '✈️' in content or 'airplane' in content.lower():
            violations.append(('icon_consistency', 'Found airplane icon (should be globe 🌐)'))
        
        # Check 5: Card consistency
        if '<div' in content and 'card' not in content and 'shadow' in content:
            violations.append(('card_style', 'Cards should use global "card" classes'))
        
        if violations:
            self.logger.warning(f"UI Consistency violations in {template_path}: {violations}")
            self.violations.extend(violations)
            return False
        
        return True
    
    def validate_all_templates(self, template_dir: str) -> Dict:
        """Validate all templates in directory"""
        import os
        from pathlib import Path
        
        results = {
            'total_templates': 0,
            'valid_templates': 0,
            'invalid_templates': 0,
            'violations': [],
        }
        
        for root, dirs, files in os.walk(template_dir):
            for file in files:
                if file.endswith('.html'):
                    filepath = os.path.join(root, file)
                    results['total_templates'] += 1
                    
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        if self.validate_template(filepath, content):
                            results['valid_templates'] += 1
                        else:
                            results['invalid_templates'] += 1
                            results['violations'].extend(
                                [{'file': filepath, 'issues': self.violations}]
                            )
                    except Exception as e:
                        self.logger.error(f"Error validating {filepath}: {str(e)}")
        
        return results


class ThemeProvider:
    """Provide global theme to all templates"""
    
    @staticmethod
    def get_theme_dict() -> Dict:
        """Return theme dictionary"""
        return GLOBAL_THEME
    
    @staticmethod
    def get_css_variables() -> str:
        """Generate CSS custom properties"""
        css = ":root {\n"
        
        for key, value in GLOBAL_THEME.items():
            # Convert snake_case to kebab-case
            css_var = key.replace('_', '-')
            css += f"  --{css_var}: {value};\n"
        
        css += "}\n"
        
        return css
    
    @staticmethod
    def get_tailwind_config() -> Dict:
        """Get Tailwind configuration"""
        return {
            'theme': {
                'extend': {
                    'colors': {
                        'primary': GLOBAL_THEME['primary_color'],
                        'secondary': GLOBAL_THEME['secondary_color'],
                        'accent': GLOBAL_THEME['accent_color'],
                    },
                    'fontFamily': {
                        'sans': [GLOBAL_THEME['font_family']],
                    },
                    'borderRadius': {
                        'lg': GLOBAL_THEME['border_radius'],
                    },
                }
            }
        }


def enforce_global_styles(template_content: str) -> str:
    """
    Process template content to enforce global styles.
    Replace old patterns with new consistent ones.
    """
    # Replace aircraft icon with globe
    template_content = template_content.replace('✈️', '🌐')
    template_content = template_content.replace('airplane', 'globe')
    
    # Ensure navbar uses global style
    if '<nav' in template_content and 'navbar' not in template_content.lower():
        template_content = template_content.replace('<nav', '<nav class="navbar"')
    
    # Ensure buttons use global classes
    template_content = template_content.replace(
        '<button>',
        '<button class="btn btn-primary">'
    )
    
    return template_content


"""
=== USAGE IN TEMPLATES ===

Main base template (base.html):
{% load zygotrip_theme %}
<!DOCTYPE html>
<html>
<head>
    <style>
        {% global_theme_css %}
    </style>
</head>
<body style="background-color: {% global_theme_color 'background_color' %}">
    {% global_navbar user=request.user %}
    <main>
        {% block content %}{% endblock %}
    </main>
</body>
</html>

Using buttons:
{% global_button "Search" url="/search/" button_type="primary" icon="search" %}

Using cards:
{% global_card title="Hotel Details" content=hotel.description %}

Using icons:
{% global_icon "location" %} {{ hotel.location }}
"""