"""
Management command: seed_holiday_calendar
Seeds the HolidayCalendar table with Indian public holidays, major festivals,
and tourism peak seasons for 2025-2026.

Usage:
    python manage.py seed_holiday_calendar
    python manage.py seed_holiday_calendar --year 2026
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction


INDIAN_HOLIDAYS_2025 = [
    # -- National Holidays
    {'date': '2025-01-01', 'name': "New Year's Day", 'type': 'national', 'multiplier': '1.8', 'state': ''},
    {'date': '2025-01-14', 'name': "Makar Sankranti", 'type': 'festival', 'multiplier': '1.4', 'state': ''},
    {'date': '2025-01-26', 'name': "Republic Day", 'type': 'national', 'multiplier': '1.6', 'state': ''},
    {'date': '2025-02-02', 'name': "Vasant Panchami", 'type': 'festival', 'multiplier': '1.2', 'state': ''},
    {'date': '2025-02-26', 'name': "Maha Shivratri", 'type': 'festival', 'multiplier': '1.3', 'state': ''},
    {'date': '2025-03-14', 'name': "Holi", 'type': 'festival', 'multiplier': '1.7', 'state': ''},
    {'date': '2025-03-30', 'name': "Ram Navami", 'type': 'festival', 'multiplier': '1.3', 'state': ''},
    {'date': '2025-04-06', 'name': "Mahavir Jayanti", 'type': 'festival', 'multiplier': '1.2', 'state': ''},
    {'date': '2025-04-14', 'name': "Dr. Ambedkar Jayanti", 'type': 'national', 'multiplier': '1.2', 'state': ''},
    {'date': '2025-04-18', 'name': "Good Friday", 'type': 'national', 'multiplier': '1.4', 'state': ''},
    {'date': '2025-04-20', 'name': "Easter Sunday", 'type': 'national', 'multiplier': '1.3', 'state': ''},
    {'date': '2025-05-01', 'name': "Labour Day", 'type': 'national', 'multiplier': '1.3', 'state': ''},
    {'date': '2025-05-12', 'name': "Buddha Purnima", 'type': 'festival', 'multiplier': '1.3', 'state': ''},
    {'date': '2025-06-07', 'name': "Eid ul-Adha", 'type': 'festival', 'multiplier': '1.5', 'state': ''},
    {'date': '2025-07-06', 'name': "Muharram", 'type': 'festival', 'multiplier': '1.2', 'state': ''},
    {'date': '2025-08-09', 'name': "Janmashtami", 'type': 'festival', 'multiplier': '1.5', 'state': ''},
    {'date': '2025-08-15', 'name': "Independence Day", 'type': 'national', 'multiplier': '1.6', 'state': ''},
    {'date': '2025-08-27', 'name': "Ganesh Chaturthi", 'type': 'festival', 'multiplier': '1.6', 'state': 'MH'},
    {'date': '2025-09-05', 'name': "Teachers' Day", 'type': 'national', 'multiplier': '1.1', 'state': ''},
    {'date': '2025-10-02', 'name': "Gandhi Jayanti", 'type': 'national', 'multiplier': '1.3', 'state': ''},
    {'date': '2025-10-02', 'name': "Navratri Begins", 'type': 'festival', 'multiplier': '1.4', 'state': ''},
    {'date': '2025-10-12', 'name': "Dussehra", 'type': 'festival', 'multiplier': '1.6', 'state': ''},
    {'date': '2025-10-20', 'name': "Diwali", 'type': 'festival', 'multiplier': '2.0', 'state': ''},
    {'date': '2025-10-21', 'name': "Diwali (Day 2)", 'type': 'festival', 'multiplier': '1.9', 'state': ''},
    {'date': '2025-10-22', 'name': "Diwali (Day 3)", 'type': 'festival', 'multiplier': '1.9', 'state': ''},
    {'date': '2025-11-05', 'name': "Guru Nanak Jayanti", 'type': 'festival', 'multiplier': '1.4', 'state': ''},
    {'date': '2025-12-25', 'name': "Christmas Day", 'type': 'national', 'multiplier': '1.8', 'state': ''},
    {'date': '2025-12-31', 'name': "New Year's Eve", 'type': 'major_event', 'multiplier': '2.0', 'state': ''},
    # -- School Holidays
    {'date': '2025-05-15', 'name': "Summer Vacation Peak", 'type': 'school_holiday', 'multiplier': '1.5', 'state': ''},
    {'date': '2025-06-01', 'name': "Summer Peak", 'type': 'tourism_peak', 'multiplier': '1.4', 'state': ''},
    {'date': '2025-06-15', 'name': "Summer End Peak", 'type': 'school_holiday', 'multiplier': '1.3', 'state': ''},
    # -- Long Weekends
    {'date': '2025-01-25', 'name': "Republic Day Long Weekend (Sat)", 'type': 'long_weekend', 'multiplier': '1.5', 'state': ''},
    {'date': '2025-04-19', 'name': "Good Friday Long Weekend (Sat)", 'type': 'long_weekend', 'multiplier': '1.5', 'state': ''},
]

INDIAN_HOLIDAYS_2026 = [
    {'date': '2026-01-01', 'name': "New Year's Day", 'type': 'national', 'multiplier': '1.8', 'state': ''},
    {'date': '2026-01-14', 'name': "Makar Sankranti", 'type': 'festival', 'multiplier': '1.4', 'state': ''},
    {'date': '2026-01-26', 'name': "Republic Day", 'type': 'national', 'multiplier': '1.6', 'state': ''},
    {'date': '2026-03-03', 'name': "Holi", 'type': 'festival', 'multiplier': '1.7', 'state': ''},
    {'date': '2026-04-03', 'name': "Good Friday", 'type': 'national', 'multiplier': '1.4', 'state': ''},
    {'date': '2026-04-14', 'name': "Dr. Ambedkar Jayanti", 'type': 'national', 'multiplier': '1.2', 'state': ''},
    {'date': '2026-05-01', 'name': "Labour Day", 'type': 'national', 'multiplier': '1.3', 'state': ''},
    {'date': '2026-08-15', 'name': "Independence Day", 'type': 'national', 'multiplier': '1.6', 'state': ''},
    {'date': '2026-10-02', 'name': "Gandhi Jayanti", 'type': 'national', 'multiplier': '1.3', 'state': ''},
    {'date': '2026-11-08', 'name': "Diwali", 'type': 'festival', 'multiplier': '2.0', 'state': ''},
    {'date': '2026-11-09', 'name': "Diwali (Day 2)", 'type': 'festival', 'multiplier': '1.9', 'state': ''},
    {'date': '2026-12-25', 'name': "Christmas Day", 'type': 'national', 'multiplier': '1.8', 'state': ''},
    {'date': '2026-12-31', 'name': "New Year's Eve", 'type': 'major_event', 'multiplier': '2.0', 'state': ''},
    {'date': '2026-05-20', 'name': "Summer Vacation Peak", 'type': 'school_holiday', 'multiplier': '1.5', 'state': ''},
]


class Command(BaseCommand):
    help = "Seed Indian public holidays and festivals into HolidayCalendar"

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=None, help="Year to seed (default: all years)")
        parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")

    def handle(self, *args, **options):
        from apps.core.models import HolidayCalendar
        from datetime import date as date_cls

        if options["clear"]:
            HolidayCalendar.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared existing holiday calendar data."))

        year = options.get("year")
        datasets = []
        if year == 2025 or year is None:
            datasets.extend(INDIAN_HOLIDAYS_2025)
        if year == 2026 or year is None:
            datasets.extend(INDIAN_HOLIDAYS_2026)

        created = 0
        updated = 0
        with transaction.atomic():
            for entry in datasets:
                obj, was_created = HolidayCalendar.objects.update_or_create(
                    date=date_cls.fromisoformat(entry["date"]),
                    holiday_name=entry["name"],
                    country="IN",
                    defaults={
                        "state": entry.get("state", ""),
                        "holiday_type": entry["type"],
                        "demand_multiplier": Decimal(entry["multiplier"]),
                        "is_active": True,
                    }
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Holiday calendar seeded: {created} created, {updated} updated."
        ))
