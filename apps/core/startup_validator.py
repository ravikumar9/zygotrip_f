"""
PHASE 6: Startup validation script
Validates critical system components before server starts
"""
import sys
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class StartupValidator:
    """Validates system configuration at startup"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_middleware_imports(self):
        """Verify all middleware classes can be imported"""
        print("\n[STARTUP] Validating middleware imports...")
        
        for middleware_path in settings.MIDDLEWARE:
            try:
                # Skip Django built-in middleware
                if middleware_path.startswith('django.'):
                    continue
                if middleware_path.startswith('whitenoise.'):
                    continue
                
                # Import the middleware class
                module_path, class_name = middleware_path.rsplit('.', 1)
                module = __import__(module_path, fromlist=[class_name])
                middleware_class = getattr(module, class_name)
                
                print(f"  ✓ {middleware_path}")
                
            except (ImportError, AttributeError) as e:
                error_msg = f"Middleware import failed: {middleware_path} - {str(e)}"
                self.errors.append(error_msg)
                print(f"  ✗ {middleware_path} - ERROR: {e}")
    
    def validate_url_patterns(self):
        """Verify URL configuration can be loaded"""
        print("\n[STARTUP] Validating URL patterns...")
        
        try:
            from django.urls import get_resolver
            resolver = get_resolver()
            
            # Test basic URL resolution
            url_patterns = resolver.url_patterns
            pattern_count = len(url_patterns)
            
            print(f"  ✓ Loaded {pattern_count} root URL patterns")
            
            # Verify critical routes exist
            critical_routes = [
                ('/', 'Homepage'),
                ('/health/', 'Health check'),
                ('/buses/', 'Buses (Phase 1)'),
                ('/packages/', 'Packages (Phase 1)'),
            ]
            
            for route, desc in critical_routes:
                try:
                    match = resolver.resolve(route)
                    print(f"  ✓ {desc}: {route}")
                except Exception as e:
                    warning_msg = f"Route not found: {route} ({desc})"
                    self.warnings.append(warning_msg)
                    print(f"  ⚠ {desc}: {route} - WARNING: {e}")
                    
        except Exception as e:
            error_msg = f"URL configuration error: {str(e)}"
            self.errors.append(error_msg)
            print(f"  ✗ URL validation failed: {e}")
    
    def validate_installed_apps(self):
        """Verify all installed apps can be imported"""
        print("\n[STARTUP] Validating INSTALLED_APPS...")
        
        for app_name in settings.INSTALLED_APPS:
            try:
                # Skip Django built-in apps
                if app_name.startswith('django.'):
                    continue

                # Handle AppConfig paths like core.apps.CoreConfig
                if '.apps.' in app_name and app_name.endswith('Config'):
                    module_path, class_name = app_name.rsplit('.', 1)
                    module = __import__(module_path, fromlist=[class_name])
                    getattr(module, class_name)
                else:
                    __import__(app_name)

                print(f"  ✓ {app_name}")

            except (ImportError, AttributeError) as e:
                error_msg = f"App import failed: {app_name} - {str(e)}"
                self.errors.append(error_msg)
                print(f"  ✗ {app_name} - ERROR: {e}")
    
    def validate_critical_settings(self):
        """Verify critical settings are configured"""
        print("\n[STARTUP] Validating critical settings...")
        
        # Check SECRET_KEY
        if not settings.SECRET_KEY or settings.SECRET_KEY == 'your-secret-key-here':
            self.warnings.append("SECRET_KEY is not configured securely")
            print("  ⚠ SECRET_KEY appears to be default/insecure")
        else:
            print("  ✓ SECRET_KEY is configured")
        
        # Check DEBUG status
        if settings.DEBUG:
            self.warnings.append("DEBUG is True - should be False in production")
            print("  ⚠ DEBUG=True (development mode)")
        else:
            print("  ✓ DEBUG=False (production mode)")
        
        # Check ALLOWED_HOSTS
        if settings.DEBUG and not settings.ALLOWED_HOSTS:
            print("  ✓ ALLOWED_HOSTS (development mode)")
        elif not settings.ALLOWED_HOSTS:
            self.errors.append("ALLOWED_HOSTS is empty in production mode")
            print("  ✗ ALLOWED_HOSTS is empty")
        else:
            print(f"  ✓ ALLOWED_HOSTS: {', '.join(settings.ALLOWED_HOSTS)}")
    
    def run_all_validations(self):
        """Run all validation checks"""
        print("\n" + "="*60)
        print("PHASE 6: STARTUP VALIDATION")
        print("="*60)
        
        self.validate_middleware_imports()
        self.validate_url_patterns()
        self.validate_installed_apps()
        self.validate_critical_settings()
        
        # Print summary
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        
        if self.errors:
            print(f"\n❌ ERRORS: {len(self.errors)}")
            for error in self.errors:
                print(f"  - {error}")
            print("\n⚠️  Server startup should be blocked!")
            return False
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        print("\n✅ All critical validations passed")
        print("="*60 + "\n")
        
        return True


def run_startup_validation():
    """Entry point for startup validation"""
    validator = StartupValidator()
    success = validator.run_all_validations()
    
    if not success:
        raise ImproperlyConfigured(
            "Startup validation failed. Fix errors before starting server."
        )
    
    return success