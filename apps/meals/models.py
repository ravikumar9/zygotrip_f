from django.db import models
from apps.core.models import TimeStampedModel


class MealPlan(TimeStampedModel):
    """
    Global meal plan catalog (Phase 5 OTA standardization).

    Standard codes:
      R      — Room Only
      R+B    — Room + Breakfast
      R+B+L/D — Room + Breakfast + Lunch or Dinner
      R+A    — Room + All Meals

    RoomMealPlan (rooms app) links a room_type to a meal_plan
    with a property-specific price modifier.
    """
    CODE_R = 'R'
    CODE_RB = 'R+B'
    CODE_RBLD = 'R+B+L/D'
    CODE_RA = 'R+A'

    CODE_CHOICES = [
        (CODE_R, 'Room Only'),
        (CODE_RB, 'Room + Breakfast'),
        (CODE_RBLD, 'Room + Breakfast + Lunch/Dinner'),
        (CODE_RA, 'Room + All Meals'),
    ]

    code = models.CharField(
        max_length=20, choices=CODE_CHOICES, unique=True,
        help_text='OTA-standard meal plan code',
    )
    name = models.CharField(max_length=100)
    display_name = models.CharField(
        max_length=150, blank=True,
        help_text='Owner-customizable display name',
    )
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = 'meals'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} — {self.name}"