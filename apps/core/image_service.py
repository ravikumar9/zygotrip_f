"""Property image optimization and variant generation service."""
import io
import logging
import os
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image

logger = logging.getLogger(__name__)


class ImageOptimizationService:
    VARIANTS = {
        'thumbnail': 320,
        'card': 640,
        'detail': 1200,
        'retina': 2400,
    }

    def _cloudfront_url(self, storage_path):
        domain = getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', '')
        if not domain:
            return storage_path
        return f"https://{domain}/{storage_path}"

    def process_property_image(self, image_file, property):
        try:
            image = Image.open(image_file).convert('RGB')
            variants = {}
            for variant, width in self.VARIANTS.items():
                img = image.copy()
                img.thumbnail((width, width * 10000), Image.Resampling.LANCZOS)

                buffer = io.BytesIO()
                img.save(buffer, format='WEBP', quality=85)
                buffer.seek(0)

                output_path = (
                    f"properties/{property.id}/{variant}_{property.id}.webp"
                )
                default_storage.save(output_path, ContentFile(buffer.read()))
                variants[f'{variant}_url'] = self._cloudfront_url(output_path)

            return variants
        except Exception as exc:
            logger.exception('Image optimization failed: %s', exc)
            raise


@shared_task
def process_new_property_image(property_id, image_path):
    from apps.hotels.models import Property

    try:
        property_obj = Property.objects.get(id=property_id)
        with default_storage.open(image_path, 'rb') as image_fp:
            variants = ImageOptimizationService().process_property_image(image_fp, property_obj)
        property_obj.image_variants = variants
        property_obj.save(update_fields=['image_variants', 'updated_at'])
        return variants
    except Exception as exc:
        logger.exception('process_new_property_image failed property_id=%s image_path=%s err=%s', property_id, image_path, exc)
        return {'error': str(exc)}
