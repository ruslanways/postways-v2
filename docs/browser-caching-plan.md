# Browser Caching Plan

This document outlines the browser caching strategy for Postways using Nginx, Cloudflare CDN, and S3.

## Architecture Overview

```
User → Cloudflare CDN → Nginx (static) → Django (dynamic)
                     → S3 (media)
```

## 1. Static Files (Nginx)

### Django Configuration

Use `ManifestStaticFilesStorage` for hashed filenames:

```python
# settings.py
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
```

### Nginx Configuration

```nginx
# Static files with hashed names (style.abc123.css)
location /static/ {
    alias /path/to/staticfiles/;
    expires 1y;
    add_header Cache-Control "public, immutable";
    add_header Vary "Accept-Encoding";

    # Enable gzip
    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml;
}
```

Cloudflare will respect these headers and cache at edge automatically.

## 2. Media Files (S3 + Cloudflare)

### Django Configuration

Set cache headers when uploading to S3:

```python
# settings.py
AWS_S3_OBJECT_PARAMETERS = {
    "CacheControl": "public, max-age=15552000",  # 6 months
}
```

### Celery Task (Optional Override)

For thumbnails that never change once created:

```python
# apps/diary/tasks.py
from django.core.files.storage import default_storage

@shared_task
def process_post_image(post_id):
    # ... existing processing code ...

    # When saving to S3, headers come from AWS_S3_OBJECT_PARAMETERS
    # Or override per-file:
    if hasattr(default_storage, 'object_parameters'):
        # For thumbnails (never change once created)
        default_storage.object_parameters = {
            "CacheControl": "public, max-age=31536000, immutable"
        }
```

Cloudflare will cache S3 responses at edge based on these headers.

## 3. HTML Views (Django → Cloudflare)

Cloudflare respects `Cache-Control` headers. Add them to views:

```python
# apps/diary/views/html.py
from django.views.decorators.cache import cache_control
from django.utils.decorators import method_decorator

# Public pages - Cloudflare will cache at edge
@method_decorator(cache_control(public=True, max_age=60, s_maxage=300), name="dispatch")
class HomeView(ListView):
    ...

@method_decorator(cache_control(public=True, max_age=60, s_maxage=300), name="dispatch")
class HomeViewPopular(ListView):
    ...

# Post detail - longer cache, use stale-while-revalidate
@method_decorator(
    cache_control(public=True, max_age=300, s_maxage=1800, stale_while_revalidate=60),
    name="dispatch"
)
class PostDetailView(DetailView):
    ...

# User profiles - shorter cache (data changes more often)
@method_decorator(cache_control(public=True, max_age=60, s_maxage=300), name="dispatch")
class AuthorDetailView(DetailView):
    ...

# Private/authenticated pages - no CDN caching
@method_decorator(cache_control(private=True, no_store=True), name="dispatch")
class PostCreateView(CreateView):
    ...
```

### Key Headers for Cloudflare

- `s-maxage` - CDN cache time (can differ from browser `max-age`)
- `stale-while-revalidate` - serve stale while fetching fresh copy
- `private` - prevents CDN caching (user-specific content)

## 4. API Responses (Django → Cloudflare)

```python
# apps/diary/views/api.py
from django.views.decorators.cache import cache_control
from django.utils.decorators import method_decorator

# API root - very stable
class RootAPIView(APIView):
    @method_decorator(cache_control(public=True, max_age=3600, s_maxage=86400))
    def get(self, request):
        ...

# Public post list
class PostAPIView(generics.ListCreateAPIView):
    @method_decorator(cache_control(public=True, max_age=60, s_maxage=300))
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

# Like batch - short cache, varies by query params
class LikeBatchAPIView(APIView):
    @method_decorator(cache_control(private=True, max_age=10))
    def get(self, request):
        ...

# Auth endpoints - never cache
class MyTokenObtainPairView(TokenObtainPairView):
    @method_decorator(cache_control(no_store=True))
    def post(self, request, *args, **kwargs):
        ...
```

## 5. Cloudflare Page Rules (Optional)

For fine-grained control beyond headers:

| URL Pattern | Cache Level | Edge TTL | Browser TTL |
|-------------|-------------|----------|-------------|
| `*/static/*` | Cache Everything | 1 month | 1 year |
| `*/media/*` | Cache Everything | 1 week | 6 months |
| `*/api/v1/posts/*` | Standard | 5 min | 1 min |
| `*/api/v1/auth/*` | Bypass | - | - |
| `/` | Standard | 5 min | 1 min |

## 6. Cache Invalidation Strategy

### Static Files

Handled automatically by hashed filenames (new hash = new URL).

### Media Files on S3

Options:
1. Cloudflare API purge on image update
2. Add version query param: `/media/image.jpg?v=1234`
3. Accept 6-month stale (images rarely change after upload)

### HTML/API

Use short `s-maxage` + `stale-while-revalidate` for graceful updates.

## Summary Table

| Target | Location | Cache-Control | Notes |
|--------|----------|---------------|-------|
| Static CSS/JS | Nginx | `public, immutable, max-age=31536000` | Hashed filenames required |
| Media images | S3 | `public, max-age=15552000` | Set via `AWS_S3_OBJECT_PARAMETERS` |
| Thumbnails | S3 | `public, immutable, max-age=31536000` | Never change once created |
| Home/Popular | Django | `public, max-age=60, s-maxage=300` | CDN caches longer |
| Post detail | Django | `public, max-age=300, s-maxage=1800` | Stable content |
| Post create/edit | Django | `private, no-store` | Never cache |
| API public | Django | `public, max-age=60, s-maxage=300` | Varies by endpoint |
| API auth | Django | `no-store` | Never cache |

## Dependencies

No new Python dependencies needed. Just:
- Configure `ManifestStaticFilesStorage` in Django
- Set `AWS_S3_OBJECT_PARAMETERS` for S3
- Configure Nginx for static files
- Optionally set Cloudflare page rules
