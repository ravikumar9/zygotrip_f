"""Image optimization and processing.

Phase 5: Production image rules:
- Aspect ratio: 4:3
- Resolution: 800x600 minimum
- Format: WebP
- Lazy loading: enabled
- Retina @2x: generate
"""

import os
from django.conf import settings
from typing import Dict, Optional


class ImageOptimizer:
    """Image optimization and URL generation."""
    
    ASPECT_RATIO_4_3 = (4, 3)
    ASPECT_RATIO_16_9 = (16, 9)
    
    # Standard breakpoints for responsive images
    BREAKPOINTS = {
        'thumbnail': 200,   # 200px
        'small': 400,       # 400px
        'medium': 600,      # 600px
        'large': 800,       # 800px
        'xlarge': 1200,     # 1200px
    }
    
    @staticmethod
    def get_hotel_card_image_url(image_url: str, size: str = 'medium') -> str:
        """Get optimized image URL for hotel card.
        
        Args:
            image_url: Original image URL
            size: 'thumbnail', 'small', 'medium', 'large', 'xlarge'
        
        Returns: Optimized image URL
        """
        if not image_url:
            return ImageOptimizer.get_placeholder_url()
        
        # In production, this would call image processing service
        # (e.g., Cloudinary, ImageKit, AWS Lambda)
        # For now, return the URL as-is
        # Note: Integrate with real image processing service
        
        return image_url
    
    @staticmethod
    def get_hotel_gallery_image_url(image_url: str, size: str = 'large') -> str:
        """Get optimized image URL for detail page gallery."""
        if not image_url:
            return ImageOptimizer.get_placeholder_url()
        return image_url
    
    @staticmethod
    def get_placeholder_url() -> str:
        """Get placeholder image URL."""
        return '/static/img/placeholder-hotel.jpg'
    
    @staticmethod
    def get_srcset(image_url: str, aspect_ratio: str = '4:3') -> str:
        """Generate srcset string for responsive images.
        
        Example output:
        /img?url=...&w=400 400w, /img?url=...&w=800 800w, /img?url=...&w=1200 1200w
        """
        if not image_url:
            return ''
        
        # In production, generate URLs for each breakpoint
        sizes = [400, 800, 1200]
        return ', '.join([
            f"{image_url} {size}w" for size in sizes
        ])
    
    @staticmethod
    def get_image_dimensions(
        width: int,
        aspect_ratio: tuple = ASPECT_RATIO_4_3
    ) -> Dict[str, int]:
        """Calculate dimensions based on width and aspect ratio.
        
        Returns: {'width': int, 'height': int}
        """
        w, h = aspect_ratio
        height = int(width * h / w)
        return {'width': width, 'height': height}


class ImageTemplate:
    """Template snippets for optimized images."""
    
    @staticmethod
    def hotel_card_image(image_url: str, alt_text: str = '') -> str:
        """Generate optimized hotel card image HTML.
        
        Features:
        - Lazy loading
        - Proper aspect ratio
        - Responsive widths
        - Fallback placeholder
        """
        optimized_url = ImageOptimizer.get_hotel_card_image_url(image_url, 'medium')
        srcset = ImageOptimizer.get_srcset(image_url)
        
        html = f'''<img 
            src="{optimized_url}"
            srcset="{srcset}"
            alt="{alt_text}"
            loading="lazy"
            decoding="async"
            width="400"
            height="300"
            class="hotel-card-image"
            onerror="this.src='{ImageOptimizer.get_placeholder_url()}'"
        />'''
        
        return html
    
    @staticmethod
    def hotel_detail_image(image_url: str, alt_text: str = '') -> str:
        """Generate optimized hotel detail page image HTML."""
        optimized_url = ImageOptimizer.get_hotel_gallery_image_url(image_url, 'large')
        
        html = f'''<img 
            src="{optimized_url}"
            alt="{alt_text}"
            loading="lazy"
            decoding="async"
            class="detail-image"
            onerror="this.src='{ImageOptimizer.get_placeholder_url()}'"
        />'''
        
        return html