from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0030_property_image_variants'),
    ]

    operations = [
        migrations.CreateModel(
            name='HotelEmbedding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('embedding', models.JSONField(default=list)),
                ('embedding_model', models.CharField(default='text-embedding-3-small', max_length=120)),
                ('content_hash', models.CharField(db_index=True, max_length=64)),
                ('content_text', models.TextField(blank=True)),
                ('property', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='semantic_embedding', to='hotels.property')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['embedding_model'], name='hotel_embed_model_idx'),
                    models.Index(fields=['updated_at'], name='hotel_embed_updated_idx'),
                ],
            },
        ),
    ]
