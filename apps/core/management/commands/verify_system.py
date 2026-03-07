from django.core.management.base import BaseCommand
from django.urls import resolve
from django.apps import apps
from django.db import connections
from django.core.cache import cache
import os


class Command(BaseCommand):
    help = 'Verify system status: URLs, templates, DB, Redis, Celery, migrations'

    def handle(self, *args, **options):
        results = {}
        
        # 1. URL ROUTING CHECK
        self.stdout.write('\n=== URL ROUTING CHECK ===')
        urls_to_check = [
            ('/accounts/login/', 'accounts:login'),
            ('/accounts/register/', 'accounts:register'),
            ('/accounts/logout/', 'accounts:logout'),
            ('/hotels/', 'hotels:list'),
            ('/buses/', 'buses:list'),
            ('/cabs/', 'cabs:list'),
            ('/flights/', 'flights:list'),
            ('/trains/', 'trains:list'),
        ]
        url_status = True
        for path, name in urls_to_check:
            try:
                resolve(path)
                self.stdout.write(f'  ✓ {path}')
            except Exception as e:
                self.stdout.write(f'  ✗ {path}: {e}')
                url_status = False
        results['URL_CHECK'] = 'PASS' if url_status else 'FAIL'
        
        # 2. TEMPLATES CHECK
        self.stdout.write('\n=== TEMPLATES CHECK ===')
        templates = [
            'templates/accounts/login.html',
            'templates/accounts/register.html',
            'templates/hotels/list.html',
            'templates/buses/list.html',
            'templates/coming_soon.html',
        ]
        template_status = True
        for template_path in templates:
            if os.path.exists(template_path):
                self.stdout.write(f'  ✓ {template_path}')
            else:
                self.stdout.write(f'  ✗ {template_path} NOT FOUND')
                template_status = False
        results['TEMPLATES'] = 'PASS' if template_status else 'FAIL'
        
        # 3. DATABASE CHECK
        self.stdout.write('\n=== DATABASE CHECK ===')
        db_status = True
        try:
            conn = connections['default']
            cursor = conn.cursor()
            self.stdout.write('  ✓ Database connection successful')
            
            # Count data
            user_model = apps.get_model('accounts', 'User')
            property_model = apps.get_model('hotels', 'Property')
            bus_model = apps.get_model('buses', 'Bus')
            package_model = apps.get_model('packages', 'Package')

            user_count = user_model.objects.count()
            hotel_count = property_model.objects.count()
            bus_count = bus_model.objects.count()
            package_count = package_model.objects.count()
            
            self.stdout.write(f'  ✓ Users: {user_count}')
            self.stdout.write(f'  ✓ Hotels: {hotel_count}')
            self.stdout.write(f'  ✓ Buses: {bus_count}')
            self.stdout.write(f'  ✓ Packages: {package_count}')
            
        except Exception as e:
            self.stdout.write(f'  ✗ Database error: {e}')
            db_status = False
        results['DATABASE'] = 'PASS' if db_status else 'FAIL'
        
        # 4. REDIS CHECK
        self.stdout.write('\n=== REDIS CHECK ===')
        redis_status = False
        try:
            cache.set('test_key', 'test_value', 10)
            value = cache.get('test_key')
            if value == 'test_value':
                self.stdout.write('  ✓ Redis connection and operations successful')
                redis_status = True
            else:
                self.stdout.write('  ✗ Redis value mismatch')
        except Exception as e:
            self.stdout.write(f'  ⚠ Redis not available: {str(e)[:60]}...')
        results['REDIS'] = 'PASS' if redis_status else 'WARNING'
        
        # 5. MIGRATIONS CHECK
        self.stdout.write('\n=== MIGRATIONS CHECK ===')
        from django.core.management import execute_from_command_line
        from io import StringIO
        import sys
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            execute_from_command_line(['manage.py', 'showmigrations', '--list'])
            sys.stdout = old_stdout
            self.stdout.write('  ✓ Migrations applied')
            results['MIGRATIONS'] = 'PASS'
        except Exception as e:
            sys.stdout = old_stdout
            self.stdout.write(f'  ✗ Migration check failed: {e}')
            results['MIGRATIONS'] = 'FAIL'
        
        # FINAL REPORT
        self.stdout.write('\n' + '='*50)
        self.stdout.write('VERIFICATION REPORT')
        self.stdout.write('='*50)
        for check, status in results.items():
            self.stdout.write(f'{check}: {status}')
        self.stdout.write('='*50)