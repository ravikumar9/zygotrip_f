"""
PHASE 7: Image Fixes
- MEDIA_URL properly mapped in urls.py
- Fallback image if missing
- Validate URL before render
- Lazy load all images
"""
from urllib.parse import urljoin
from django.conf import settings
import os
import logging

logger = logging.getLogger(__name__)


class ImageHandler:
    """Image loading, validation, and fallback management"""
    
    # Fallback image URL (transparent 1x1 or placeholder)
    DEFAULT_FALLBACK = '/static/images/placeholder-room.png'
    PROPERTY_FALLBACK = '/static/images/placeholder-property.png'
    
    @staticmethod
    def get_media_url():
        """Get configured MEDIA_URL (must be set in urls.py)"""
        return getattr(settings, 'MEDIA_URL', '/media/')
    
    @staticmethod
    def validate_image_url(image_url, url_type='room_image'):
        """
        Validate image URL before rendering.
        Returns: {valid: bool, url: str (absolute or fallback), message: str}
        """
        if not image_url or image_url == '' or image_url == 'None':
            return {
                'valid': False,
                'url': ImageHandler.DEFAULT_FALLBACK,
                'message': 'Empty image URL',
                'lazy': True
            }
        
        image_url = str(image_url).strip()
        
        # If URL starts with /, assume relative and add domain
        if image_url.startswith('/'):
            return {
                'valid': True,
                'url': image_url,
                'message': 'Valid relative URL',
                'lazy': True  # Enable lazy loading
            }
        
        # If URL is absolute HTTP(S), allow it
        if image_url.startswith('http://') or image_url.startswith('https://'):
            return {
                'valid': True,
                'url': image_url,
                'message': 'Valid absolute URL',
                'lazy': True
            }
        
        # If URL contains {MEDIA_ROOT}, it might be a database path
        # Prepend MEDIA_URL
        if not image_url.startswith(ImageHandler.get_media_url()):
            # Assume it's a filename, prepend MEDIA_URL
            image_url = ImageHandler.get_media_url() + image_url
        
        return {
            'valid': True,
            'url': image_url,
            'message': 'URL constructed from MEDIA_URL',
            'lazy': True
        }
    
    @staticmethod
    def get_safe_image_url(image_url_or_field, fallback=None, url_type='room_image'):
        """
        Get a validated, safe image URL with fallback.
        
        Args:
            image_url_or_field: str (URL) or Django FileField instance
            fallback: str (URL to use if image_url invalid/missing)
            url_type: str ('room_image' or 'property_image')
            
        Returns: {'url': str, 'lazy': bool}
        """
        fallback = fallback or (
            ImageHandler.PROPERTY_FALLBACK if url_type == 'property_image'
            else ImageHandler.DEFAULT_FALLBACK
        )
        
        try:
            # If it's a FileField
            if hasattr(image_url_or_field, 'url'):
                url = image_url_or_field.url
            else:
                url = str(image_url_or_field)
            
            validation = ImageHandler.validate_image_url(url, url_type)
            
            return {
                'url': validation['url'] if validation['valid'] else fallback,
                'lazy': validation.get('lazy', True),
                'alt_text': f"{url_type.replace('_', ' ').title()} - Loading...",
            }
        
        except Exception as e:
            logger.error(f"Error processing image URL: {str(e)}")
            return {
                'url': fallback,
                'lazy': True,
                'alt_text': f"{url_type.replace('_', ' ').title()} - Not available",
            }
    
    @staticmethod
    def build_image_srcset(image_url, sizes='200 400 600'):
        """
        Build responsive image srcset for lazy loading.
        
        For modern websites showing same image at multiple sizes,
        srcset allows browser to load optimal size.
        
        Returns: {
            'src': str,
            'srcset': str,
            'sizes': str,
            'loading': 'lazy'
        }
        """
        validation = ImageHandler.validate_image_url(image_url)
        url = validation['url']
        
        # Build srcset with common sizes
        # Note: This works well if using CDN with size parameters
        # e.g., /media/image.jpg?w=200 or /cdn/image?w=200&h=200&fit=cover
        
        return {
            'src': url,
            'srcset': url,  # Could be enhanced for CDN: f"{url}?w=200, {url}?w=400"
            'sizes': '(max-width: 600px) 200px, (max-width: 1000px) 400px, 600px',
            'loading': 'lazy',
            'decoding': 'async',  # Allows browser to decode image asynchronously
        }
    
    @staticmethod
    def get_property_images(property_obj, limit=5):
        """
        Get property images with validation and lazy loading.
        
        Returns: [{url, lazy, alt_text}, ...]
        """
        images = []
        
        try:
            property_images = property_obj.propertyimage_set.all()[:limit]
            
            for img in property_images:
                images.append(
                    ImageHandler.get_safe_image_url(img.image_url, url_type='property_image')
                )
        
        except Exception as e:
            logger.warning(f"Failed to load property images: {str(e)}")
        
        # Ensure at least fallback
        if not images:
            images.append({
                'url': ImageHandler.PROPERTY_FALLBACK,
                'lazy': False,
                'alt_text': 'Property image not available'
            })
        
        return images
    
    @staticmethod
    def get_room_images(room_type, limit=4):
        """
        Get room-specific images with validation and lazy loading.
        
        Returns: [{url, lazy, alt_text}, ...]
        """
        images = []
        
        try:
            room_images = room_type.roomimage_set.all()[:limit]
            
            for img in room_images:
                images.append(
                    ImageHandler.get_safe_image_url(img.image_url, url_type='room_image')
                )
        
        except Exception as e:
            logger.warning(f"Failed to load room images: {str(e)}")
        
        # If no room images, try property fallback
        if not images:
            try:
                property_images = room_type.property.propertyimage_set.all()[:1]
                if property_images:
                    images.append(
                        ImageHandler.get_safe_image_url(
                            property_images[0].image_url,
                            fallback=ImageHandler.DEFAULT_FALLBACK,
                            url_type='room_image'
                        )
                    )
            except Exception:
                pass
        
        # Final fallback
        if not images:
            images.append({
                'url': ImageHandler.DEFAULT_FALLBACK,
                'lazy': False,
                'alt_text': 'Room image not available'
            })
        
        return images
