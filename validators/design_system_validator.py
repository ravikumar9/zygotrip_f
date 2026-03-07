"""
Zygotrip Design System Enforcement Validator
Ensures strict compliance: NO inline styles, NO hardcoded colors (except in tokens)
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple


class DesignSystemValidator:
    """Validates design system compliance across templates and CSS"""
    
    # Properties that should use design tokens
    TOKEN_REQUIRED_PATTERNS = {
        'color': r'color\s*:\s*',
        'background-color': r'background-color\s*:\s*',
        'background': r'background\s*:\s*(?!url|linear-gradient)',  # Allow URLs and gradients in design tokens
        'border-color': r'border-color\s*:\s*',
        'border': r'border-color\s*:\s*',
    }
    
    # Allowed hardcoded values
    ALLOWED_HARDCODED = {
        'border': ['1px', '2px', '4px', '0', 'none', 'solid', 'dashed'],  # Sizes and styles OK
        'padding': ['var(', 'px', 'rem', 'em', '0'],  # But prefer tokens
        'margin': ['var(', 'px', 'rem', 'em', '0'],
        'border-radius': ['var(', 'px', 'rem', 'em', '0', '50%'],
        'font-size': ['var(', 'px', 'rem', 'em'],  # Prefer tokens
        'rgba': ['var('],  # MUST use var() for transparency instead of rgba(0,0,0,0.1)
    }
    
    # Files that are exempt from inline style enforcement (demo/preview only)
    EXEMPT_FILES = {
        'component-library-preview.html',
    }
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.inline_style_violations = []
        self.hardcoded_color_violations = []
        self.non_token_color_violations = []
        
    def validate_templates(self) -> Dict:
        """Scan all HTML templates for inline styles"""
        templates_dir = self.workspace_root / 'templates'
        
        if not templates_dir.exists():
            return {}
        
        violations = {
            'files_with_inline_styles': {},
            'total_inline_style_count': 0,
            'violation_details': []
        }
        
        for html_file in templates_dir.rglob('*.html'):
            # Skip exempt files
            if html_file.name in self.EXEMPT_FILES:
                continue
            
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Find all style= attributes
            file_violations = []
            for line_num, line in enumerate(lines, 1):
                matches = re.finditer(r'style="([^"]*)"', line)
                for match in matches:
                    style_content = match.group(1)
                    file_violations.append({
                        'line': line_num,
                        'style': style_content,
                        'context': line.strip()[:100]
                    })
            
            if file_violations:
                rel_path = html_file.relative_to(self.workspace_root)
                violations['files_with_inline_styles'][str(rel_path)] = len(file_violations)
                violations['total_inline_style_count'] += len(file_violations)
                violations['violation_details'].extend([
                    {
                        'file': str(rel_path),
                        **v
                    } for v in file_violations
                ])
        
        return violations
    
    def validate_colors(self) -> Dict:
        """Scan templates for hardcoded colors"""
        templates_dir = self.workspace_root / 'templates'
        
        violations = {
            'files_with_hardcoded_colors': {},
            'total_color_violations': 0,
            'violation_details': []
        }
        
        # Pattern for hex colors and rgb/rgba
        color_pattern = re.compile(
            r'(?:^|[^a-zA-Z])(?:'
             r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?|'  # short or long hex
            r'rgba?\([^)]*\)'  # rgb() or rgba()
            r')',
            re.IGNORECASE
        )
        
        for html_file in templates_dir.rglob('*.html'):
            if html_file.name in self.EXEMPT_FILES:
                continue
            
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            file_violations = []
            for line_num, line in enumerate(lines, 1):
                # Skip lines with var( - those are using tokens correctly
                if 'var(--' in line:
                    continue
                
                # Look for hex colors or rgb/rgba
                hex_pattern = re.compile(r'(?:^|[^a-zA-Z])#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?')
                rgba_pattern = re.compile(r'rgba?\([^)]*\)')
                
                hex_matches = hex_pattern.finditer(line)
                for match in hex_matches:
                    color = match.group().strip('#').lstrip()
                    # Skip data URLs and other false positives
                    if len(color) in [3, 6]:
                        file_violations.append({
                            'line': line_num,
                            'color': '#' + color,
                            'type': 'hex',
                            'context': line.strip()[:100]
                        })
                
                rgba_matches = rgba_pattern.finditer(line)
                for match in rgba_matches:
                    rgba_val = match.group()
                    # Skip if it's inside var()
                    if 'var(' not in rgba_val:
                        file_violations.append({
                            'line': line_num,
                            'color': rgba_val,
                            'type': 'rgba',
                            'context': line.strip()[:100]
                        })
            
            if file_violations:
                rel_path = html_file.relative_to(self.workspace_root)
                violations['files_with_hardcoded_colors'][str(rel_path)] = len(file_violations)
                violations['total_color_violations'] += len(file_violations)
                violations['violation_details'].extend([
                    {
                        'file': str(rel_path),
                        **v
                    } for v in file_violations
                ])
        
        return violations
    
    def validate_css_files(self) -> Dict:
        """Scan CSS files for hardcoded colors outside design-tokens.css"""
        static_css_dir = self.workspace_root / 'static' / 'css'
        
        violations = {
            'files_with_hex_colors': {},
            'total_color_violations': 0,
            'violation_details': [],
            'note': 'Only checking non-design-tokens.css files'
        }
        
        if not static_css_dir.exists():
            return violations
        
        for css_file in static_css_dir.rglob('*.css'):
            # design-tokens.css is allowed to have hardcoded colors
            if css_file.name == 'design-tokens.css':
                continue
            
            with open(css_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            file_violations = []
            for line_num, line in enumerate(lines, 1):
                # Skip comments and url()
                if line.strip().startswith('/*') or line.strip().startswith('*') or 'url(' in line:
                    continue
                
                # Skip lines using var()
                if 'var(--' in line:
                    continue
                
                # Find hex colors
                hex_pattern = re.compile(r'#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?')
                hex_matches = hex_pattern.finditer(line)
                
                for match in hex_matches:
                    color = match.group()
                    file_violations.append({
                        'line': line_num,
                        'color': color,
                        'context': line.strip()[:100]
                    })
            
            if file_violations:
                rel_path = css_file.relative_to(self.workspace_root)
                violations['files_with_hex_colors'][str(rel_path)] = len(file_violations)
                violations['total_color_violations'] += len(file_violations)
                violations['violation_details'].extend([
                    {
                        'file': str(rel_path),
                        **v
                    } for v in file_violations
                ])
        
        return violations
    
    def generate_compliance_report(self) -> Dict:
        """Generate complete compliance report"""
        template_issues = self.validate_templates()
        color_issues = self.validate_colors()
        css_issues = self.validate_css_files()
        
        total_inline_styles = template_issues.get('total_inline_style_count', 0)
        total_hardcoded_colors = color_issues.get('total_color_violations', 0)
        total_css_failures = css_issues.get('total_color_violations', 0)
        
        # Calculate enforcement status
        enforcement_ready = (
            total_inline_styles == 0 and 
            total_hardcoded_colors == 0 and 
            total_css_failures == 0
        )
        
        return {
            'phase': 'PHASE_3.5_ENFORCEMENT',
            'timestamp': str(Path('__timestamp__')),
            'enforcement_status': 'PASSED' if enforcement_ready else 'FAILED',
            'enforcement_ready': enforcement_ready,
            'metrics': {
                'inline_styles_remaining': total_inline_styles,
                'hardcoded_colors_remaining': total_hardcoded_colors,
                'non_token_colors': total_css_failures,
                'total_violations': total_inline_styles + total_hardcoded_colors + total_css_failures
            },
            'template_validation': template_issues,
            'color_validation': color_issues,
            'css_validation': css_issues,
            'gate_status': {
                'phase_4_ready': enforcement_ready,
                'requirements_met': {
                    'zero_inline_styles': total_inline_styles == 0,
                    'zero_hardcoded_colors': total_hardcoded_colors == 0,
                    'zero_non_token_colors': total_css_failures == 0
                }
            }
        }


def validate_design_system(workspace_root: str = None) -> Dict:
    """Utility function to run validation"""
    if workspace_root is None:
        workspace_root = os.getcwd()
    
    validator = DesignSystemValidator(workspace_root)
    return validator.generate_compliance_report()


if __name__ == '__main__':
    import json
    report = validate_design_system()
    print(json.dumps(report, indent=2))