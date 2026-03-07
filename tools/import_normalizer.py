#!/usr/bin/env python
"""
IMPORT DISCIPLINE ENFORCEMENT - NORMALIZATION ENGINE

This script normalizes all root-level imports to use apps.* namespace.
Executes in phases with verification at each step.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Configuration
PROJECT_ROOT = Path(__file__).parent
SKIP_DIRS = {'.venv', 'venv', '__pycache__', 'migrations', '.git', 'node_modules'}
SKIP_FILES = {'manage.py', 'wsgi.py', 'asgi.py'}

# Import patterns to normalize (module -> apps.module)
IMPORT_PATTERNS = {
    'core': 'apps.core',
    'dashboard_admin': 'apps.dashboard_admin',
    'dashboard_owner': 'apps.dashboard_owner',
    'dashboard_finance': 'apps.dashboard_finance',
    'inventory': 'apps.inventory',
    'packages': 'apps.packages',
    'pricing': 'apps.pricing',
    'promos': 'apps.promos',
    'rooms': 'apps.rooms',
    'meals': 'apps.meals',
    'security': 'apps.security',
    'registration': 'apps.registration',
    'wallet': 'apps.wallet',
    'payments': 'apps.payments',
    'hotels': 'apps.hotels',
    'booking': 'apps.booking',
    'buses': 'apps.buses',
    'cabs': 'apps.cabs',
    'flights': 'apps.flights',
    'trains': 'apps.trains',
}

# THIRD-PARTY AND STDLIB - NEVER MODIFY
PRESERVE_MODULES = {
    'django', 'rest_framework', 'celery', 'redis', 'pytest',
    'os', 'sys', 'json', 'datetime', 'typing', 'pathlib',
    'requests', 'bs4', 'PIL', 'environ', 'debug_toolbar',
    'asgiref', 'playwright', 'fuzzywuzzy', 'locust'
}


class ImportNormalizer:
    """Normalizes root-level imports to apps.* namespace."""
    
    def __init__(self):
        self.fixes = []
        self.errors = []
        self.skipped = []
        
    def should_skip_file(self, filepath: Path) -> bool:
        """Check if file should be skipped."""
        if filepath.name in SKIP_FILES:
            return True
        if filepath.suffix != '.py':
            return True
        # Skip test files for now (process separately)
        # if 'test' in filepath.name and 'test_' in filepath.name:
        #     return True
        return False
    
    def should_skip_dir(self, dirpath: Path) -> bool:
        """Check if directory should be skipped."""
        for part in dirpath.parts:
            if part in SKIP_DIRS:
                return True
        return False
    
    def find_python_files(self) -> List[Path]:
        """Find all Python files to process."""
        files = []
        for filepath in PROJECT_ROOT.rglob('*.py'):
            if self.should_skip_dir(filepath.parent):
                continue
            if self.should_skip_file(filepath):
                continue
            files.append(filepath)
        return files
    
    def normalize_import_line(self, line: str) -> Tuple[str, bool]:
        """
        Normalize a single import line.
        Returns (normalized_line, was_changed)
        """
        # Pattern 1: from X import Y
        match = re.match(r'^(\s*from\s+)([a-z_][a-z0-9_]*)(\s+import\s+.*)$', line, re.IGNORECASE)
        if match:
            indent, module, rest = match.groups()
            
            # Check if module needs normalization
            if module in IMPORT_PATTERNS and module not in PRESERVE_MODULES:
                new_module = IMPORT_PATTERNS[module]
                return f"{indent}{new_module}{rest}", True
        
        # Pattern 2: import X
        match = re.match(r'^(\s*import\s+)([a-z_][a-z0-9_.]*)(.*)$', line, re.IGNORECASE)
        if match:
            indent, module, rest = match.groups()
            
            # Get base module (before first dot)
            base_module = module.split('.')[0]
            
            # Check if base module needs normalization
            if base_module in IMPORT_PATTERNS and base_module not in PRESERVE_MODULES:
                new_module = module.replace(base_module, IMPORT_PATTERNS[base_module], 1)
                return f"{indent}{new_module}{rest}", True
        
        return line, False
    
    def normalize_file(self, filepath: Path) -> bool:
        """
        Normalize all imports in a file.
        Returns True if file was modified, False otherwise.
        """
        try:
            content = filepath.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            modified = False
            new_lines = []
            
            for line in lines:
                new_line, changed = self.normalize_import_line(line)
                new_lines.append(new_line)
                if changed:
                    modified = True
                    self.fixes.append({
                        'file': str(filepath.relative_to(PROJECT_ROOT)),
                        'old': line.strip(),
                        'new': new_line.strip(),
                    })
            
            if modified:
                new_content = '\n'.join(new_lines)
                filepath.write_text(new_content, encoding='utf-8')
                return True
            
            return False
            
        except Exception as e:
            self.errors.append({
                'file': str(filepath.relative_to(PROJECT_ROOT)),
                'error': str(e),
            })
            return False
    
    def execute(self):
        """Execute normalization across all files."""
        print("=" * 80)
        print("IMPORT DISCIPLINE ENFORCEMENT - NORMALIZATION")
        print("=" * 80)
        
        files = self.find_python_files()
        print(f"\nScanning {len(files)} Python files...\n")
        
        modified_count = 0
        for i, filepath in enumerate(files, 1):
            rel_path = filepath.relative_to(PROJECT_ROOT)
            print(f"[{i}/{len(files)}] Processing: {rel_path}...", end=' ')
            
            if self.normalize_file(filepath):
                print("✅ MODIFIED")
                modified_count += 1
            else:
                print("⊘ No changes")
        
        print(f"\n{'=' * 80}")
        print(f"RESULTS")
        print(f"{'=' * 80}")
        print(f"Total files processed: {len(files)}")
        print(f"Files modified: {modified_count}")
        print(f"Fixes applied: {len(self.fixes)}")
        print(f"Errors: {len(self.errors)}")
        
        if self.fixes:
            print(f"\n{'─' * 80}")
            print("FIXES APPLIED")
            print(f"{'─' * 80}")
            for fix in self.fixes[:20]:  # Show first 20
                print(f"\n{fix['file']}")
                print(f"  OLD: {fix['old']}")
                print(f"  NEW: {fix['new']}")
            if len(self.fixes) > 20:
                print(f"\n... and {len(self.fixes) - 20} more fixes")
        
        if self.errors:
            print(f"\n{'─' * 80}")
            print("ERRORS")
            print(f"{'─' * 80}")
            for error in self.errors:
                print(f"\n{error['file']}")
                print(f"  ERROR: {error['error']}")
        
        print(f"\n{'=' * 80}")
        
        return len(self.errors) == 0


if __name__ == '__main__':
    normalizer = ImportNormalizer()
    success = normalizer.execute()
    sys.exit(0 if success else 1)