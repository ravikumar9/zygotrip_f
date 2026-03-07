from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SearchIndex",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("type", models.CharField(choices=[("city", "City"), ("area", "Area"), ("property", "Property")], max_length=20)),
                ("property_count", models.IntegerField(blank=True, null=True)),
                ("slug", models.SlugField(max_length=220)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["type", "name"], name="search_se_type_2d4980_idx"),
                    models.Index(fields=["slug"], name="search_se_slug_6ab32f_idx"),
                ],
                "unique_together": {("type", "slug")},
            },
        ),
    ]
