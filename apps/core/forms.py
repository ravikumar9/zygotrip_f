"""
Base form mixins for design system consistency
"""
from django import forms


class StyledFormMixin:
    """
    Mixin that automatically applies ui-input class to all form widgets.
    Add this to any form to ensure it matches the design system.
    
    Usage:
        class MyForm(StyledFormMixin, forms.Form):
            name = forms.CharField()
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        for field_name, field in self.fields.items():
            widget = field.widget
            
            # Get existing classes or empty string
            existing_classes = widget.attrs.get('class', '')
            
            # Add ui-input class if not already present
            if 'ui-input' not in existing_classes:
                classes = existing_classes.split() if existing_classes else []
                classes.append('ui-input')
                widget.attrs['class'] = ' '.join(classes)
            
            # Add ui-label class to label if needed (handled in template, but can be set here)
            # Labels are typically rendered in templates, so this is optional