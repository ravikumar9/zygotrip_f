"""
Management command to bulk approve all properties and mark agreements signed.
This enables the entire system to function for testing/demo purposes.
"""
from django.core.management.base import BaseCommand
from apps.hotels.models import Property


class Command(BaseCommand):
	help = 'Bulk approve all properties and mark agreements signed'

	def add_arguments(self, parser):
		parser.add_argument(
			'--confirm',
			action='store_true',
			help='Confirm the action (prevents accidental bulk updates)'
		)

	def handle(self, *args, **options):
		if not options['confirm']:
			count = Property.objects.exclude(status='approved').count()
			self.stdout.write(
				self.style.WARNING(
					f'This will approve {count} properties. Use --confirm to proceed.'
				)
			)
			return

		# Update all properties
		updated = Property.objects.filter(status='pending').update(status='approved', agreement_signed=True)
		
		# Also approve any suspended ones for demo
		suspended_updated = Property.objects.filter(status='suspended').update(status='approved', agreement_signed=True)
		
		total_updated = updated + suspended_updated
		
		self.stdout.write(
			self.style.SUCCESS(
				f'✓ Approved {total_updated} properties\n'
				f'  - {updated} from pending\n'
				f'  - {suspended_updated} from suspended'
			)
		)
		
		# Verify
		total_properties = Property.objects.count()
		approved_properties = Property.objects.filter(status='approved', agreement_signed=True).count()
		
		self.stdout.write(
			self.style.SUCCESS(
				f'\n✓ Final status: {approved_properties}/{total_properties} properties approved'
			)
		)
