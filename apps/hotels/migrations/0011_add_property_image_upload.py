from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hotels", "0010_remove_propertyamenityfilter_amenity_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="propertyimage",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="hotels/"),
        ),
        migrations.AlterField(
            model_name="propertyimage",
            name="image_url",
            field=models.URLField(blank=True, null=True),
        ),
    ]
