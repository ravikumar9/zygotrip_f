"""
Zygotrip Design System - Automated Inline Style Refactoring Tool
Converts inline styles to utility classes and design tokens
"""

import re
from pathlib import Path
from typing import Tuple, Dict, List


class InlineStyleRefactor:
    """Automatically refactors inline styles to utility classes"""
    
    # Mapping of inline style patterns to utility classes
    STYLE_MAPPINGS = {
        # Text alignment
        r'text-align:\s*center': 'text-center',
        r'text-align:\s*left': 'text-left',
        r'text-align:\s*right': 'text-right',
        r'text-align:\s*justify': 'text-justify',
        
        # Display
        r'display:\s*flex': 'd-flex',
        r'display:\s*inline-flex': 'd-inline-flex',
        r'display:\s*grid': 'd-grid',
        r'display:\s*block': 'd-block',
        r'display:\s*none': 'd-none',
        r'display:\s*inline-block': 'd-inline-block',
        
        # Flex direction
        r'flex-direction:\s*column': 'flex-col',
        r'flex-direction:\s*row': 'flex-row',
        r'flex-direction:\s*row-reverse': 'flex-reverse',
        r'flex-wrap:\s*wrap': 'flex-wrap',
        r'flex-wrap:\s*nowrap': 'flex-nowrap',
        
        # Justify content
        r'justify-content:\s*center': 'justify-center',
        r'justify-content:\s*space-between': 'justify-between',
        r'justify-content:\s*space-around': 'justify-around',
        r'justify-content:\s*flex-start': 'justify-start',
        r'justify-content:\s*flex-end': 'justify-end',
        
        # Align items
        r'align-items:\s*center': 'align-center',
        r'align-items:\s*flex-start': 'align-start',
        r'align-items:\s*flex-end': 'align-end',
        r'align-items:\s*baseline': 'align-baseline',
        r'align-items:\s*stretch': 'align-stretch',
        
        # Overflow
        r'overflow:\s*hidden': 'overflow-hidden',
        r'overflow:\s*auto': 'overflow-auto',
        r'overflow-x:\s*auto': 'overflow-x-auto',
        r'overflow-y:\s*auto': 'overflow-y-auto',
        
        # Position
        r'position:\s*relative': 'relative',
        r'position:\s*absolute': 'absolute',
        r'position:\s*sticky': 'sticky',
        
        # Border radius
        r'border-radius:\s*var\(--radius-sm\)': 'rounded-sm',
        r'border-radius:\s*var\(--radius-md\)': 'rounded',
        r'border-radius:\s*var\(--radius-lg\)': 'rounded-lg',
        r'border-radius:\s*var\(--radius-full\)': 'rounded-full',
        
        # Font weight
        r'font-weight:\s*600': 'font-semibold',
        r'font-weight:\s*700': 'font-bold',
        r'font-weight:\s*normal': 'font-normal',
        
        # List styles
        r'list-style:\s*none': 'list-none',
        r'padding:\s*0;\s*margin:\s*0': 'p-0 m-0',
        
        # Width/Height
        r'width:\s*100%': 'w-full',
        r'height:\s*100%': 'h-full',
        r'height:\s*auto': 'h-auto',
        
        # Border
        r'border-bottom:\s*1px\s+solid\s+var\(--color-border\)': 'border-bottom',
        r'border-top:\s*1px\s+solid\s+var\(--color-border\)': 'border-top',
        r'border:\s*1px\s+solid\s+var\(--color-border\)': 'border',
        r'border:\s*none': 'border-none',
    }
    
    # Patterns to convert to token-based spacing
    SPACING_PATTERNS = {
        r'padding:\s*var\(--space-(\d+)\)': lambda m: f'p-{m.group(1)}',
        r'margin:\s*var\(--space-(\d+)\)': lambda m: f'm-{m.group(1)}',
        r'padding-top:\s*var\(--space-(\d+)\)': lambda m: f'pt-{m.group(1)}',
        r'padding-bottom:\s*var\(--space-(\d+)\)': lambda m: f'pb-{m.group(1)}',
        r'padding-left:\s*var\(--space-(\d+)\)': lambda m: f'pl-{m.group(1)}',
        r'padding-right:\s*var\(--space-(\d+)\)': lambda m: f'pr-{m.group(1)}',
        r'margin-top:\s*var\(--space-(\d+)\)': lambda m: f'mt-{m.group(1)}',
        r'margin-bottom:\s*var\(--space-(\d+)\)': lambda m: f'mb-{m.group(1)}',
        r'margin-left:\s*var\(--space-(\d+)\)': lambda m: f'ml-{m.group(1)}',
        r'margin-right:\s*var\(--space-(\d+)\)': lambda m: f'mr-{m.group(1)}',
        r'gap:\s*var\(--space-(\d+)\)': lambda m: f'gap-{m.group(1)}',
    }
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.refactored_files = []
        self.conversion_log = []
    
    def extract_style_attribute(self, style_str: str) -> Dict[str, str]:
        """Parse style attribute into key-value pairs"""
        styles = {}
        # Split by semicolon, handling nested content
        parts = style_str.split(';')
        for part in parts:
            if ':' in part:
                key, value = part.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                if key and value:
                    styles[key] = value
            
        return styles
    
    def styles_to_classes(self, styles: Dict[str, str]) -> Tuple[List[str], Dict[str, str]]:
        """Convert styles dictionary to utility classes"""
        classes = []
        remaining_styles = {}
        
        for prop, value in styles.items():
            converted = False
            
            # Try pattern-based conversions
            style_str = f'{prop}: {value}'
            
            # Check static mappings
            for pattern, utility_class in self.STYLE_MAPPINGS.items():
                if re.search(pattern, style_str, re.IGNORECASE):
                    classes.append(utility_class)
                    converted = True
                    break
            
            # Check spacing patterns
            if not converted:
                for pattern, replacement in self.SPACING_PATTERNS.items():
                    match = re.search(pattern, style_str, re.IGNORECASE)
                    if match:
                        utility_class = replacement(match)
                        classes.append(utility_class)
                        converted = True
                        break
            
            # If not converted, keep as remaining style
            if not converted:
                remaining_styles[prop] = value
        
        return classes, remaining_styles
    
    def refactor_html_file(self, html_path: Path) -> Tuple[str, int]:
        """Refactor all inline styles in an HTML file"""
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        original_content = content
        style_count = 0
        
        # Find all style attributes
        def replace_style(match):
            nonlocal style_count
            style_attr = match.group(1)
            
            # Parse the styles
            styles = self.extract_style_attribute(style_attr)
            classes, remaining = self.styles_to_classes(styles)
            
            # Build replacement
            result = ''
            if classes:
                result += f' class="{" ".join(classes)}"'
                style_count += 1
            
            # If some styles remain (not convertible), keep them
            if remaining:
                result_styles = '; '.join(f'{k}: {v}' for k, v in remaining.items())
                result += f' style="{result_styles}"'
            
            return result
        
        # Replace style attributes
        # This regex finds style="..." but needs careful handling
        pattern = r'\sstyle="([^"]*)"'
        content = re.sub(pattern, replace_style, content)
        
        if content != original_content:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return html_path.relative_to(self.workspace_root), style_count
        
        return None, 0
    
    def refactor_templates_directory(self) -> Dict:
        """Refactor all HTML templates"""
        templates_dir = self.workspace_root / 'templates'
        
        results = {
            'refactored_files': [],
            'total_styles_converted': 0,
            'exempt_files': [],
        }
        
        # Exempt files from refactoring
        exempt = {'component-library-preview.html'}
        
        for html_file in templates_dir.rglob('*.html'):
            if html_file.name in exempt:
                results['exempt_files'].append(str(html_file.relative_to(self.workspace_root)))
                continue
            
            refactored_path, converted = self.refactor_html_file(html_file)
            if refactored_path:
                results['refactored_files'].append({
                    'file': str(refactored_path),
                    'styles_converted': converted
                })
                results['total_styles_converted'] += converted
        
        return results


def refactor_all_templates(workspace_root: str) -> Dict:
    """Utility function"""
    refactor = InlineStyleRefactor(workspace_root)
    return refactor.refactor_templates_directory()


if __name__ == '__main__':
    import json
    results = refactor_all_templates('c:\\Users\\ravi9\\Downloads\\Zy\\zygotrip')
    print(json.dumps(results, indent=2))