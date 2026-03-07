from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.hotels.models import Category


class Command(BaseCommand):
	help = 'Seed property categories for marketplace'

	def handle(self, *args, **options):
		categories = [
			{
				'name': 'Beach Vacations',
				'description': 'Coastal properties with ocean views',
				'icon': '🏖️'
			},
			{
				'name': 'Weekend Getaways',
				'description': 'Short-term weekend retreats',
				'icon': '🎒'
			},
			{
				'name': 'Mountains Calling',
				'description': 'Himalayan and hill station properties',
				'icon': '⛰️'
			},
			{
				'name': 'Stay Like Royals',
				'description': 'Luxury heritage hotels and palaces',
				'icon': '👑'
			},
			{
				'name': 'Indian Pilgrimages',
				'description': 'Properties near religious sites',
				'icon': '🕉️'
			},
			{
				'name': 'Party Destinations',
				'description': 'Nightlife and entertainment hubs',
				'icon': '🎉'
			},
		]

		created_count = 0
		for cat_data in categories:
			slug = slugify(cat_data['name'])
			category, created = Category.objects.get_or_create(
				slug=slug,
				defaults={
					'name': cat_data['name'],
					'description': cat_data['description'],
					'icon': cat_data['icon']
				}
			)
			if created:
				created_count += 1
				self.stdout.write(self.style.SUCCESS(f'✓ Created category: {category.name}'))
			else:
				self.stdout.write(self.style.WARNING(f'→ Category already exists: {category.name}'))

		self.stdout.write(self.style.SUCCESS(f'\n✅ Seeding complete: {created_count} new categories created'))


