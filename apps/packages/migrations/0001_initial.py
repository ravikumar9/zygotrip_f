from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PackageCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("name", models.CharField(max_length=120, unique=True)),
                ("slug", models.SlugField(blank=True, unique=True)),
                ("description", models.TextField(blank=True)),
            ],
            options={
                "verbose_name_plural": "Package Categories",
            },
        ),
        migrations.CreateModel(
            name="Package",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("name", models.CharField(max_length=160)),
                ("slug", models.SlugField(blank=True, unique=True)),
                ("description", models.TextField()),
                ("destination", models.CharField(max_length=120)),
                ("duration_days", models.PositiveIntegerField(default=3)),
                ("base_price", models.DecimalField(decimal_places=2, max_digits=12)),
                ("rating", models.DecimalField(decimal_places=1, default=4.3, max_digits=3)),
                ("review_count", models.PositiveIntegerField(default=0)),
                ("image_url", models.URLField(blank=True)),
                ("inclusions", models.TextField(blank=True)),
                ("exclusions", models.TextField(blank=True)),
                ("max_group_size", models.PositiveIntegerField(default=20)),
                ("difficulty_level", models.CharField(choices=[("easy", "Easy"), ("moderate", "Moderate"), ("challenging", "Challenging")], default="moderate", max_length=20)),
                ("hotel_included", models.BooleanField(default=True)),
                ("meals_included", models.BooleanField(default=True)),
                ("transport_included", models.BooleanField(default=True)),
                ("guide_included", models.BooleanField(default=False)),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="packages.packagecategory")),
                ("provider", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PackageImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("image_url", models.URLField()),
                ("is_featured", models.BooleanField(default=False)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("package", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="images", to="packages.package")),
            ],
            options={
                "ordering": ["-is_featured", "display_order"],
            },
        ),
        migrations.CreateModel(
            name="PackageItinerary",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_active", models.BooleanField(default=True)),
                ("day_number", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=160)),
                ("description", models.TextField()),
                ("accommodation", models.CharField(blank=True, max_length=160)),
                ("meals_included", models.CharField(choices=[("N", "No meals"), ("B", "Breakfast"), ("L", "Lunch"), ("D", "Dinner"), ("BLD", "All meals")], default="N", max_length=5)),
                ("package", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="itinerary", to="packages.package")),
            ],
            options={
                "ordering": ["day_number"],
            },
        ),
    ]
