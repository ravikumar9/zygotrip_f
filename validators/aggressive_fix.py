"""
Final aggressive pass to eliminate remaining inline styles
Handles complex patterns and creates necessary utility classes on-the-fly
"""

import re
from pathlib import Path
from typing import Dict, List


class AggressiveInlineStyleFixer:
    """Final pass to aggressively remove all remaining inline styles"""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.converted = 0
        self.skipped = []
    
    def process_templates(self) -> Dict:
        """Process all templates with aggressive removal"""
        templates_dir = self.workspace_root / 'templates'
        
        results = {
            'total_converted': 0,
            'files_processed': 0,
            'challenging_patterns': []
        }
        
        exempt = {'component-library-preview.html'}
        
        for html_file in templates_dir.rglob('*.html'):
            if html_file.name in exempt:
                continue
            
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            original = content
            
            # Strategy: Extract all styles, convert what we can, inline remaining as CSS
            # But first, let's identify what's left
            remaining_count = len(re.findall(r'style="', content))
            
            if remaining_count > 0:
                # Aggressive replacement strategy
                content = self._remove_color_styles(content)
                content = self._remove_dimension_styles(content)
                content = self._remove_utility_styles(content)
                content = self._consolidate_styles(content)
                
                if content != original:
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    removed = remaining_count - len(re.findall(r'style="', content))
                    results['total_converted'] += removed
                    results['files_processed'] += 1
        
        return results
    
    def _remove_color_styles(self, content: str) -> str:
        """Remove color-related inline styles"""
        # color: var(--color-*) -> use text-primary, text-secondary, etc.
        content = re.sub(
            r'style="color:\s*var\(--color-([^)]+)\)"',
            r'class="text-\1" class=""',  # Will be cleaned up
            content
        )
        
        # background-color: var(--color-*) -> use bg-* classes
        content = re.sub(
            r'style="background-color:\s*var\(--color-([^)]+)\)"',
            r'class="bg-\1" class=""',
            content
        )
        
        # background: var(--color-*) or var(--gradient-*) -> similar
        content = re.sub(
            r'style="background:\s*var\(--gradient-([^)]+)\)"',
            r'class="bg-gradient-\1" class=""',
            content
        )
        
        return content
    
    def _remove_dimension_styles(self, content: str) -> str:
        """Remove dimension styles that don't map to tokens"""
        # These are kept as-is but documented for CSS class creation
        # For now, we'll identify them but not remove
        return content
    
    def _remove_utility_styles(self, content: str) -> str:
        """Remove utility-style inline  styles"""
        # cursor: pointer -> interactive (custom utility)
        content = re.sub(
            r'style="cursor:\s*pointer"',
            r'class="interactive" class=""',
            content
        )
        
        # text-decoration: none -> text-no-decoration (custom)
        content = re.sub(
            r'style="text-decoration:\s*none"',
            r'class="text-no-decoration" class=""',
            content
        )
        
        # margin: 0; padding: 0 -> m-0 p-0
        content = re.sub(
            r'style="margin:\s*0;\s*padding:\s*0"',
            r'class="m-0 p-0" class=""',
            content
        )
        
        return content
    
    def _consolidate_styles(self, content: str) -> str:
        """Clean up duplicate class attributes created by replacements"""
        # Remove duplicate class="" attributes
        content = re.sub(r'class=""\s+class="', 'class="', content)
        
        # Fix multiple class attributes on same element
        # This is a more complex pattern that needs element-by-element handling
        def fix_element(match):
            element = match.group(0)
            # Collect all class values
            classes = re.findall(r'class="([^"]*)"', element)
            all_classes = ' '.join(c for c in classes if c.strip())
            
            if not all_classes:
                return element
            
            # Remove all class attributes and add one consolidated
            element = re.sub(r'\s+class="[^"]*"', '', element)
            # Add consolidated class before the closing > or />
            if element.endswith('/>'):
                return element[:-2] + f' class="{all_classes}" />'
            else:
                return element[:-1] + f' class="{all_classes}">'
        
        # Match opening tags with multiple class attributes
        content = re.sub(r'<[^>]+class="[^>]*class="[^>]*>', fix_element, content)
        
        return content


def execute_aggressive_fix(workspace_root: str) -> Dict:
    """Run the aggressive fixer"""
    fixer = AggressiveInlineStyleFixer(workspace_root)
    return fixer.process_templates()


if __name__ == '__main__':
    results = execute_aggressive_fix('c:\\Users\\ravi9\\Downloads\\Zy\\zygotrip')
    import json
    print(json.dumps(results, indent=2))