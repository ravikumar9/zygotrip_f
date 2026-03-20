"""Semantic hotel search built on OpenAI embeddings."""
import hashlib
import logging
import math
from typing import Iterable

import requests
from django.conf import settings

from apps.hotels.models import HotelEmbedding, Property

logger = logging.getLogger('zygotrip.hotels.semantic')


def _normalize_text(property_obj: Property) -> str:
    parts = [
        property_obj.name or '',
        property_obj.description or '',
        property_obj.property_type or '',
        property_obj.city.name if property_obj.city_id else '',
        property_obj.area or '',
        property_obj.landmark or '',
        ' '.join(property_obj.tags or []),
    ]
    return ' | '.join(part.strip() for part in parts if part and part.strip())


def _cosine_similarity(a: Iterable[float], b: Iterable[float]) -> float:
    a_list = list(a)
    b_list = list(b)
    if not a_list or not b_list or len(a_list) != len(b_list):
        return 0.0

    dot = sum(x * y for x, y in zip(a_list, b_list))
    norm_a = math.sqrt(sum(x * x for x in a_list))
    norm_b = math.sqrt(sum(y * y for y in b_list))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_embedding(text: str) -> list[float]:
    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    model = getattr(settings, 'OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is not configured')

    response = requests.post(
        'https://api.openai.com/v1/embeddings',
        json={'model': model, 'input': text},
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return payload['data'][0]['embedding']


def upsert_hotel_embedding(property_obj: Property) -> HotelEmbedding | None:
    text = _normalize_text(property_obj)
    if not text:
        return None

    content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    existing = HotelEmbedding.objects.filter(property=property_obj).first()
    if existing and existing.content_hash == content_hash and existing.embedding:
        return existing

    try:
        vector = build_embedding(text)
    except Exception as exc:
        logger.warning('Embedding build failed for property=%s: %s', property_obj.id, exc)
        return None

    model = getattr(settings, 'OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
    embed, _ = HotelEmbedding.objects.update_or_create(
        property=property_obj,
        defaults={
            'embedding': vector,
            'embedding_model': model,
            'content_hash': content_hash,
            'content_text': text,
        },
    )
    return embed


def semantic_search_hotels(query: str, limit: int = 10):
    query = (query or '').strip()
    if not query:
        return []

    query_vector = build_embedding(query)
    rows = HotelEmbedding.objects.select_related('property', 'property__city').filter(
        property__status='approved',
        property__agreement_signed=True,
        is_active=True,
    )

    scored = []
    for row in rows:
        if not row.embedding:
            continue
        score = _cosine_similarity(query_vector, row.embedding)
        scored.append((score, row))

    scored.sort(key=lambda item: item[0], reverse=True)

    results = []
    for score, row in scored[:limit]:
        p = row.property
        results.append({
            'property_id': p.id,
            'slug': p.slug,
            'name': p.name,
            'city': p.city.name if p.city_id else '',
            'area': p.area,
            'rating': float(p.rating or 0),
            'semantic_score': round(float(score), 6),
        })
    return results
