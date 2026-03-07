"""
Enhanced inline style refactoring with more pattern coverage
"""

import re
from pathlib import Path
from typing import Tuple, Dict, List


class EnhancedInlineStyleRefactor:
    """Enhanced version with more conversion patterns"""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
    
    def refactor_file(self, html_path: Path) -> int:
        """Aggressively refactor inline styles"""
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original = content
        converted_count = 0
        
        def replace_style(match):
            nonlocal converted_count
            full_match = match.group(0)  # e.g., style="..."
            style_val = match.group(1)   # e.g., ...content...
            
            # Skip empty styles
            if not style_val.strip():
                return full_match
            
            # Build replacement dict
            classes = []
            remaining_parts = []
            
            # Parse style properties
            properties = self._parse_style_string(style_val)
            
            for prop, value in properties:
                utility_class = self._convert_to_class(prop, value)
                if utility_class:
                    classes.extend(utility_class.split())
                    converted_count += 1
                else:
                    remaining_parts.append(f'{prop}: {value}')
            
            # Build result HTML
            if not classes and not remaining_parts:
                return ''
            
            result = ''
            if classes:
                result += f' class="{" ".join(set(classes))}"'  # Remove duplicates
            if remaining_parts:
                # Only keep if necessary
                result += f' style="{"; ".join(remaining_parts)}"'
            
            return result
        
        # Find and replace all style attributes
        pattern = r'\s*style="([^"]*)"'
        content = re.sub(pattern, replace_style, content)
        
        # Save if changed
        if content != original:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return converted_count
    
    def _parse_style_string(self, style_str: str) -> List[Tuple[str, str]]:
        """Parse CSS property declarations"""
        properties = []
        # Split by semicolon carefully
        parts = style_str.split(';')
        
        for part in parts:
            part = part.strip()
            if ':' in part:
                prop, value = part.split(':', 1)
                prop = prop.strip().lower()
                value = value.strip()
                if prop and value:
                    properties.append((prop, value))
        
        return properties
    
    def _convert_to_class(self, prop: str, value: str) -> str:
        """Convert property to utility class(es)"""
        # Flex/Grid
        if prop == 'display':
            if value == 'flex':
                return 'd-flex'
            elif value == 'grid':
                return 'd-grid'
            elif value == 'none':
                return 'd-none'
            elif value == 'block':
                return 'd-block'
            elif value == 'inline-block':
                return 'd-inline-block'
        
        # Text alignment
        if prop == 'text-align':
            return {
                'center': 'text-center',
                'left': 'text-left',
                'right': 'text-right',
                'justify': 'text-justify'
            }.get(value, '')
        
        # Overflow
        if prop == 'overflow':
            return {
                'hidden': 'overflow-hidden',
                'auto': 'overflow-auto'
            }.get(value, '')
        
        # Position
        if prop == 'position':
            return {
                'relative': 'relative',
                'absolute': 'absolute',
                'sticky': 'sticky'
            }.get(value, '')
        
        # Width/Height
        if prop == 'width':
            if value == '100%':
                return 'w-full'
            elif value == 'auto':
                return ''
        
        if prop == 'height':
            if value == '100%':
                return 'h-full'
            elif value == 'auto':
                return ''
        
        # Border radius
        if prop == 'border-radius':
            if 'var(--radius-sm)' in value:
                return 'rounded-sm'
            elif 'var(--radius-md)' in value:
                return 'rounded'
            elif 'var(--radius-lg)' in value:
                return 'rounded-lg'
            elif 'var(--radius-full)' in value or value == '50%':
                return 'rounded-full'
        
        # Borders
        if prop == 'border' and 'var(--color-border)' in value:
            if '1px' in value:
                return 'border'
            elif '2px' in value:
                return 'border'
        
        if prop == 'border-bottom' and 'var(--color-border)' in value:
            return 'border-bottom'
        
        if prop == 'border-top' and 'var(--color-border)' in value:
            return 'border-top'
        
        if prop == 'border-left' and 'var(--color-border)' in value:
            return 'border-left'
        
        if prop == 'border-right' and 'var(--color-border)' in value:
            return 'border-right'
        
        # Flex properties
        if prop == 'flex-direction':
            if value == 'column':
                return 'flex-col'
            elif value == 'row':
                return 'flex-row'
        
        if prop == 'flex-wrap':
            if value == 'wrap':
                return 'flex-wrap'
            elif value == 'nowrap':
                return 'flex-nowrap'
        
        if prop == 'justify-content':
            mapping = {
                'center': 'justify-center',
                'space-between': 'justify-between',
                'space-around': 'justify-around',
                'flex-start': 'justify-start',
                'flex-end': 'justify-end',
            }
            return mapping.get(value, '')
        
        if prop == 'align-items':
            mapping = {
                'center': 'align-center',
                'flex-start': 'align-start',
                'flex-end': 'align-end',
                'baseline': 'align-baseline',
                'stretch': 'align-stretch',
            }
            return mapping.get(value, '')
        
        if prop == 'align-self':
            mapping = {
                'center': 'align-self-center',
                'flex-start': 'align-self-start',
                'flex-end': 'align-self-end',
            }
            return mapping.get(value, '')
        
        # Spacing with tokens - try to extract numbers
        # margin-bottom: var(--space-6) -> mb-6
        spacing_match = re.search(r'var\(--space-(\d+)\)', value)
        if spacing_match:
            space_value = spacing_match.group(1)
            if prop == 'margin':
                return f'm-{space_value}'
            elif prop == 'margin-top':
                return f'mt-{space_value}'
            elif prop == 'margin-bottom':
                return f'mb-{space_value}'
            elif prop == 'margin-left':
                return f'ml-{space_value}'
            elif prop == 'margin-right':
                return f'mr-{space_value}'
            elif prop == 'padding':
                return f'p-{space_value}'
            elif prop == 'padding-top':
                return f'pt-{space_value}'
            elif prop == 'padding-bottom':
                return f'pb-{space_value}'
            elif prop == 'padding-left':
                return f'pl-{space_value}'
            elif prop == 'padding-right':
                return f'pr-{space_value}'
            elif prop == 'gap':
                return f'gap-{space_value}'
        
        # Margin/Padding with combinations
        if prop == 'margin-top' and prop == 'margin-bottom':
            if 'var(--space-' in value:
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    return f'my-{match.group(1)}'
        
        # Font weight
        if prop == 'font-weight':
            if value in ['600', 'semibold']:
                return 'font-semibold'
            elif value in ['700', 'bold']:
                return 'font-bold'
            elif value in ['400', 'normal']:
                return 'font-normal'
        
        # Font size with tokens
        if prop == 'font-size' and 'var(--fs-' in value:
            # Extract the fs value
            match = re.search(r'var\(--fs-(\w+)\)', value)
            if match:
                fs_name = match.group(1)
                mapping = {
                    'xs': 'text-xs',
                    'sm': 'text-sm',
                    'base': 'text-base',
                    'lg': 'text-lg',
                    'xl': 'text-xl',
                    '2xl': 'text-2xl',
                    '3xl': 'text-3xl',
                    '4xl': 'text-4xl',
                    '5xl': 'text-5xl',
                }
                return mapping.get(fs_name, '')
        
        # List styles
        if prop == 'list-style':
            if value == 'none':
                return 'list-none'
        
        # Check if padding is for margin: 0 - in that case
        if (prop == 'padding' or prop == 'margin') and value == '0':
            return 'p-0' if prop == 'padding' else 'm-0'
        
        return ''  # Not convertible
    
    def refactor_all(self) -> Dict:
        """Refactor all templates"""
        templates_dir = self.workspace_root / 'templates'
        
        results = {
            'total_refactored': 0,
            'total_converted': 0,
            'file_details': []
        }
        
        exempt = {'component-library-preview.html'}
        
        for html_file in sorted(templates_dir.rglob('*.html')):
            if html_file.name in exempt:
                continue
            
            converted = self.refactor_file(html_file)
            if converted > 0:
                results['total_converted'] += converted
                results['file_details'].append({
                    'file': str(html_file.relative_to(self.workspace_root)),
                    'converted': converted
                })
            
            results['total_refactored'] += 1
        
        return results


if __name__ == '__main__':
    refactor = EnhancedInlineStyleRefactor('c:\\Users\\ravi9\\Downloads\\Zy\\zygotrip')
    results = refactor.refactor_all()
    import json
    print(json.dumps(results, indent=2))