"""
Complete Inline Style Refactoring Tool
Removes ALL remaining inline styles from templates
"""

import os
import re
from pathlib import Path
from typing import Dict, List


class CompleteStyleRefactor:
    """Aggressive and comprehensive inline style removal"""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.templates_dir = self.workspace_root / 'templates'
        self.exempt_files = {'component-library-preview.html'}
        
    def convert_style_to_classes(self, style_content: str) -> str:
        """Convert inline style content to utility classes"""
        classes = []
        
        # Remove all whitespace for easier parsing
        style_content = re.sub(r'\s+', '', style_content)
        
        # Split by semicolons
        declarations = [d.strip() for d in style_content.split(';') if d.strip()]
        
        for decl in declarations:
            if ':' not in decl:
                continue
                
            prop, value = decl.split(':', 1)
            prop = prop.strip()
            value = value.strip()
            
            # Text alignment
            if prop == 'text-align':
                if value == 'center':
                    classes.append('text-center')
                elif value == 'left':
                    classes.append('text-left')
                elif value == 'right':
                    classes.append('text-right')
            
            # Display properties
            elif prop == 'display':
                if value == 'flex':
                    classes.append('d-flex')
                elif value == 'grid':
                    classes.append('d-grid')
                elif value == 'block':
                    classes.append('d-block')
                elif value == 'none':
                    classes.append('d-none')
                elif value == 'inline-flex':
                    classes.append('d-inline-flex')
            
            # Flex direction
            elif prop == 'flex-direction':
                if value == 'column':
                    classes.append('flex-col')
                elif value == 'row':
                    classes.append('flex-row')
            
            # Justify content
            elif prop == 'justify-content':
                if value == 'center':
                    classes.append('justify-center')
                elif value == 'space-between':
                    classes.append('justify-between')
                elif value == 'space-around':
                    classes.append('justify-around')
                elif value == 'flex-start' or value == 'start':
                    classes.append('justify-start')
                elif value == 'flex-end' or value == 'end':
                    classes.append('justify-end')
            
            # Align items
            elif prop == 'align-items':
                if value == 'center':
                    classes.append('align-center')
                elif value == 'flex-start' or value == 'start':
                    classes.append('align-start')
                elif value == 'flex-end' or value == 'end':
                    classes.append('align-end')
                elif value == 'baseline':
                    classes.append('align-baseline')
                elif value == 'stretch':
                    classes.append('align-stretch')
            
            # Overflow
            elif prop == 'overflow':
                if value == 'hidden':
                    classes.append('overflow-hidden')
                elif value == 'auto':
                    classes.append('overflow-auto')
            
            elif prop == 'overflow-x':
                if value == 'auto':
                    classes.append('overflow-x-auto')
            
            elif prop == 'overflow-y':
                if value == 'auto':
                    classes.append('overflow-y-auto')
            
            # Position
            elif prop == 'position':
                if value == 'relative':
                    classes.append('relative')
                elif value == 'absolute':
                    classes.append('absolute')
                elif value == 'sticky':
                    classes.append('sticky')
            
            # Font weight
            elif prop == 'font-weight':
                if value in ['300', 'light']:
                    classes.append('font-light')
                elif value in ['400', 'normal']:
                    classes.append('font-normal')
                elif value in ['600', 'semibold']:
                    classes.append('font-semibold')
                elif value in ['700', 'bold']:
                    classes.append('font-bold')
            
            # Font size with tokens
            elif prop == 'font-size':
                match = re.search(r'var\(--fs-(\w+)\)', value)
                if match:
                    size = match.group(1)
                    classes.append(f'text-{size}')
            
            # Color properties with tokens
            elif prop == 'color':
                match = re.search(r'var\(--color-text-(\w+)\)', value)
                if match:
                    color = match.group(1)
                    classes.append(f'text-{color}')
                else:
                    match = re.search(r'var\(--color-(\w+)-(\d+)\)', value)
                    if match:
                        color_name = match.group(1)
                        shade = match.group(2)
                        classes.append(f'text-{color_name}')
            
            # Background color with tokens
            elif prop == 'background-color' or (prop == 'background' and 'var(--color' in value):
                if 'var(--color-bg-' in value:
                    match = re.search(r'var\(--color-bg-(\w+)\)', value)
                    if match:
                        bg = match.group(1)
                        classes.append(f'bg-{bg}')
                else:
                    match = re.search(r'var\(--color-(\w+)', value)
                    if match:
                        color = match.group(1)
                        classes.append(f'bg-{color}')
            
            # Border radius with tokens
            elif prop == 'border-radius':
                match = re.search(r'var\(--radius-(\w+)\)', value)
                if match:
                    radius = match.group(1)
                    classes.append(f'rounded-{radius}')
                elif value == '50%':
                    classes.append('rounded-full')
            
            # Border
            elif prop == 'border':
                if value == 'none' or value == '0':
                    classes.append('border-none')
                elif 'var(--color' in value:
                    classes.append('border')
            
            # Gap with tokens
            elif prop == 'gap':
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    space = match.group(1)
                    classes.append(f'gap-{space}')
            
            # Padding with tokens (all sides)
            elif prop == 'padding':
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    space = match.group(1)
                    classes.append(f'p-{space}')
            
            # Padding individual sides
            elif prop == 'padding-top':
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    space = match.group(1)
                    classes.append(f'pt-{space}')
            
            elif prop == 'padding-bottom':
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    space = match.group(1)
                    classes.append(f'pb-{space}')
            
            elif prop == 'padding-left':
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    space = match.group(1)
                    classes.append(f'pl-{space}')
            
            elif prop == 'padding-right':
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    space = match.group(1)
                    classes.append(f'pr-{space}')
            
            # Margin with tokens (all sides)
            elif prop == 'margin':
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    space = match.group(1)
                    classes.append(f'm-{space}')
                elif value == '0':
                    classes.append('m-0')
            
            # Margin individual sides
            elif prop == 'margin-top':
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    space = match.group(1)
                    classes.append(f'mt-{space}')
                elif value == '0':
                    classes.append('mt-0')
            
            elif prop == 'margin-bottom':
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    space = match.group(1)
                    classes.append(f'mb-{space}')
                elif value == '0':
                    classes.append('mb-0')
            
            elif prop == 'margin-left':
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    space = match.group(1)
                    classes.append(f'ml-{space}')
                elif value == 'auto':
                    classes.append('ml-auto')
                elif value == '0':
                    classes.append('ml-0')
            
            elif prop == 'margin-right':
                match = re.search(r'var\(--space-(\d+)\)', value)
                if match:
                    space = match.group(1)
                    classes.append(f'mr-{space}')
                elif value == 'auto':
                    classes.append('mr-auto')
                elif value == '0':
                    classes.append('mr-0')
            
            # Width
            elif prop == 'width':
                if value == '100%':
                    classes.append('w-full')
            
            # Height
            elif prop == 'height':
                if value == '100%':
                    classes.append('h-full')
            
            # List style
            elif prop == 'list-style':
                if value == 'none':
                    classes.append('list-none')
        
        return ' '.join(classes)
    
    def refactor_file(self, file_path: Path) -> int:
        """Refactor a single template file, return number of conversions"""
        if file_path.name in self.exempt_files:
            return 0
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        conversions = 0
        
        # Find all style attributes
        style_pattern = re.compile(r'style="([^"]*)"', re.IGNORECASE)
        
        matches = list(style_pattern.finditer(content))
        
        # Process matches in reverse order to maintain string indices
        for match in reversed(matches):
            style_content = match.group(1)
            classes = self.convert_style_to_classes(style_content)
            
            if classes:
                # Find if there's already a class attribute nearby
                start = match.start()
                # Look backwards for opening tag
                tag_start = content.rfind('<', 0, start)
                tag_portion = content[tag_start:match.end()]
                
                # Check if class attribute exists in this tag
                class_match = re.search(r'class="([^"]*)"', tag_portion)
                
                if class_match:
                    # Add to existing classes
                    existing_classes = class_match.group(1)
                    new_classes = f"{existing_classes} {classes}".strip()
                    
                    # Replace the class attribute
                    old_class_attr = class_match.group(0)
                    new_class_attr = f'class="{new_classes}"'
                    content = content[:tag_start] + tag_portion.replace(old_class_attr, new_class_attr, 1).replace(match.group(0), '', 1) + content[match.end():]
                else:
                    # Add new class attribute and remove style
                    content = content[:match.start()] + f'class="{classes}"' + content[match.end():]
                
                conversions += 1
            else:
                # If we couldn't convert, just remove the style attribute
                content = content[:match.start()] + content[match.end():]
                conversions += 1
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return conversions
    
    def refactor_all(self) -> Dict:
        """Refactor all templates"""
        results = {
            'total_files': 0,
            'total_conversions': 0,
            'files_modified': []
        }
        
        for html_file in self.templates_dir.rglob('*.html'):
            conversions = self.refactor_file(html_file)
            
            if conversions > 0:
                rel_path = str(html_file.relative_to(self.workspace_root))
                results['files_modified'].append({
                    'file': rel_path,
                    'conversions': conversions
                })
                results['total_conversions'] += conversions
            
            results['total_files'] += 1
        
        return results


if __name__ == '__main__':
    import json
    refactor = CompleteStyleRefactor(r'c:\Users\ravi9\Downloads\Zy\zygotrip')
    results = refactor.refactor_all()
    print(json.dumps(results, indent=2))