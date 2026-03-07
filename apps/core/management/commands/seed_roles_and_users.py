from decimal import Decimal
from django.apps import apps
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.utils import OperationalError

User = apps.get_model('accounts', 'User')
Role = apps.get_model('accounts', 'Role')
Permission = apps.get_model('accounts', 'Permission')
RolePermission = apps.get_model('accounts', 'RolePermission')
UserRole = apps.get_model('accounts', 'UserRole')
Wallet = apps.get_model('wallet', 'Wallet')
try:
    WalletTransaction = apps.get_model('wallet', 'WalletTransaction')
except LookupError:
    WalletTransaction = None


class Command(BaseCommand):
    help = 'Seed all roles and test users (customers and owners).'

    def handle(self, *args, **options):
        self.stdout.write('Seeding roles and users...')
        
        # Seed roles and permissions
        self._seed_roles_and_permissions()
        
        # Seed test users
        self._seed_test_users()
        
        self.stdout.write(self.style.SUCCESS('✓ Roles and users seeding complete'))

    def _seed_roles_and_permissions(self):
        """Create all system roles with their permissions."""
        
        # Define roles and their permissions
        roles_config = {
            'customer': {
                'name': 'Customer',
                'description': 'Regular platform user - can book travel',
                'permissions': [
                    ('view_bookings', 'View own bookings'),
                    ('book_hotel', 'Book hotels'),
                    ('book_bus', 'Book buses'),
                    ('book_cab', 'Book cabs'),
                    ('book_flight', 'Book flights'),
                    ('book_train', 'Book trains'),
                    ('book_package', 'Book packages'),
                    ('view_wallet', 'View wallet balance'),
                    ('view_transactions', 'View wallet transactions'),
                ]
            },
            'owner': {
                'name': 'Owner/Operator',
                'description': 'Property/service owner - can manage listings',
                'permissions': [
                    ('manage_property', 'Manage hotel properties'),
                    ('manage_bus', 'Manage bus services'),
                    ('manage_cab', 'Manage cab services'),
                    ('view_owner_bookings', 'View bookings for owned services'),
                    ('manage_pricing', 'Manage dynamic pricing'),
                    ('view_owner_wallet', 'View owner settlement wallet'),
                ]
            },
            'admin': {
                'name': 'Administrator',
                'description': 'System administrator with full access',
                'permissions': [
                    ('view_all_bookings', 'View all bookings'),
                    ('manage_users', 'Manage all users'),
                    ('manage_roles', 'Manage roles and permissions'),
                    ('view_analytics', 'View platform analytics'),
                    ('manage_promotions', 'Manage promotions and coupons'),
                    ('access_admin_panel', 'Access Django admin panel'),
                    ('view_all_wallets', 'View all wallet data'),
                ]
            },
            'support': {
                'name': 'Support Agent',
                'description': 'Customer support staff',
                'permissions': [
                    ('view_all_bookings', 'View all bookings'),
                    ('view_customer_info', 'View customer information'),
                    ('manage_disputes', 'Manage refund disputes'),
                    ('process_refunds', 'Process refunds'),
                ]
            }
        }
        
        for role_code, role_info in roles_config.items():
            # Create or update role
            role, created = Role.objects.get_or_create(
                code=role_code,
                defaults={
                    'name': role_info['name'],
                    'description': role_info['description'],
                }
            )
            
            status = '(created)' if created else '(exists)'
            self.stdout.write(f'  ✓ Role: {role.name} {status}')
            
            # Create permissions and link to role
            for perm_code, perm_name in role_info['permissions']:
                permission, _ = Permission.objects.get_or_create(
                    code=perm_code,
                    defaults={'name': perm_name}
                )
                
                RolePermission.objects.get_or_create(
                    role=role,
                    permission=permission
                )

    def _seed_test_users(self):
        """Create test users with different roles."""
        
        test_users = [
            # Customers
            {
                'email': 'customer1@zygotrip.com',
                'full_name': 'Amit Kumar',
                'phone': '9876543210',
                'role': 'customer',
                'wallet_initial': Decimal('5000.00'),
            },
            {
                'email': 'customer2@zygotrip.com',
                'full_name': 'Priya Singh',
                'phone': '9876543211',
                'role': 'customer',
                'wallet_initial': Decimal('3500.00'),
            },
            {
                'email': 'customer3@zygotrip.com',
                'full_name': 'Rahul Patel',
                'phone': '9876543212',
                'role': 'customer',
                'wallet_initial': Decimal('2000.00'),
            },
            {
                'email': 'customer4@zygotrip.com',
                'full_name': 'Neha Gupta',
                'phone': '9876543213',
                'role': 'customer',
                'wallet_initial': Decimal('7500.00'),
            },
            {
                'email': 'customer5@zygotrip.com',
                'full_name': 'Vikram Sharma',
                'phone': '9876543214',
                'role': 'customer',
                'wallet_initial': Decimal('1500.00'),
            },
            
            # Owners
            {
                'email': 'owner1@zygotrip.com',
                'full_name': 'Hotel Group India',
                'phone': '9876543220',
                'role': 'owner',
                'wallet_initial': Decimal('50000.00'),
            },
            {
                'email': 'owner2@zygotrip.com',
                'full_name': 'Express Buses Ltd',
                'phone': '9876543221',
                'role': 'owner',
                'wallet_initial': Decimal('75000.00'),
            },
            {
                'email': 'owner3@zygotrip.com',
                'full_name': 'Cab Services Delhi',
                'phone': '9876543222',
                'role': 'owner',
                'wallet_initial': Decimal('45000.00'),
            },
            {
                'email': 'owner4@zygotrip.com',
                'full_name': 'Tourism Packages Pro',
                'phone': '9876543223',
                'role': 'owner',
                'wallet_initial': Decimal('60000.00'),
            },
            
            # Support staff
            {
                'email': 'support@zygotrip.com',
                'full_name': 'Support Team',
                'phone': '9876543230',
                'role': 'support',
                'wallet_initial': Decimal('0.00'),
            },
        ]
        
        for user_data in test_users:
            email = user_data.pop('email')
            role_code = user_data.pop('role')
            wallet_initial = user_data.pop('wallet_initial')
            
            # Get or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={**user_data, 'is_active': True}
            )
            
            if created:
                user.set_unusable_password()
                user.save(update_fields=['password', 'updated_at'])
            
            # Assign role
            role = Role.objects.get(code=role_code)
            UserRole.objects.get_or_create(user=user, role=role)
            
            # Create or update wallet (skip if wallet tables not migrated)
            try:
                wallet, wallet_created = Wallet.objects.get_or_create(
                    user=user,
                    defaults={'balance': wallet_initial}
                )

                if wallet_created and WalletTransaction is not None:
                    # Log initial wallet funding
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        transaction_type='credit',
                        amount=wallet_initial,
                        description='Initial wallet funding',
                        reference_id=f'INIT-{user.id}',
                        status='completed'
                    )
            except OperationalError:
                self.stdout.write('  ⚠ Wallet tables missing; skipping wallet seed')
            
            status = '(created)' if created else '(exists)'
            self.stdout.write(f'  ✓ User: {user.email} [{role.name}] {status}')