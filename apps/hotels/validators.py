"""Validators for hotels app models."""

from django.core.exceptions import ValidationError

# Known image CDN hostnames that serve images without file extensions in the URL path.
KNOWN_IMAGE_CDNS = (
    'picsum.photos',
    'images.unsplash.com',
    'source.unsplash.com',
    'cloudinary.com',
    'res.cloudinary.com',
    'imagekit.io',
    'ik.imagekit.io',
    'loremflickr.com',
)


def validate_https_image_url(value):
    """Validate that URL is HTTPS and ends with a valid image extension,
    or originates from a known image CDN that serves images without extensions."""
    if not value:
        return

    valid_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.gif')

    if not value.startswith('https://'):
        raise ValidationError('Image URL must start with https://')

    # Allow known image CDNs that serve extensionless image URLs
    from urllib.parse import urlparse
    hostname = urlparse(value).hostname or ''
    if any(hostname == cdn or hostname.endswith('.' + cdn) for cdn in KNOWN_IMAGE_CDNS):
        return

    # Check if URL ends with valid extension (ignoring query params)
    url_without_params = value.split('?')[0] if '?' in value else value

    if not any(url_without_params.lower().endswith(ext) for ext in valid_extensions):
        raise ValidationError(
            'Image URL must end with a valid image extension: ' + ', '.join(valid_extensions)
        )
