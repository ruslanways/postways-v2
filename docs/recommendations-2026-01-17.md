# Project Structure Recommendations
**Generated:** 2026-01-17 12:50 UTC

## Summary

The project is well-organized and follows Django best practices in most areas.

---

## Strengths

- Clean separation of concerns (models, views, serializers, permissions)
- Proper environment-driven configuration with `django-environ`
- Hybrid architecture (traditional views + REST API)
- Real-time WebSocket capability with Channels
- Background task processing with Celery
- Docker-ready with multi-stage build and health checks
- Custom user model done correctly

---

## Recommended Improvements

### 1. Split `views.py` (498 lines)

The monolithic views file should be broken into modules:

```
apps/diary/views/
├── __init__.py      # Re-exports all views
├── html_views.py    # Traditional Django CBVs
├── api_views.py     # DRF API views
└── mixins.py        # Shared mixins
```

### 2. Clean up test structure

You have both `tests.py` and `tests/` directory. Remove the legacy `tests.py` file and keep only the `tests/` directory.

### 3. Fix typo in forms

`CutomSetPasswordForm` → `CustomSetPasswordForm` in `forms.py`

### 4. Remove debug artifacts

- `print()` statements in `middleware.py:19` and `signals.py:10`
- Empty signal handler in `signals.py` that just passes

### 5. Security concern - ALLOWED_HOSTS

`ALLOWED_HOSTS = ["*"]` is set regardless of DEBUG mode. Restrict this in production.

### 6. Performance considerations

| Issue | Location | Suggestion |
|-------|----------|------------|
| DB write every request | `UserLastRequestMiddleware` | Batch updates or use cache with periodic flush |
| Sync image processing | `Post.save()` | Move thumbnail generation to Celery task |
| Repeated like count queries | Views | Add Redis caching for like counts |

### 7. Redis client in views

Direct Redis instantiation in `views.py:63` should be moved to a service layer or utility module for better testability.

### 8. Missing from dependencies

`django-debug-toolbar` is in middleware but not visible in `pyproject.toml`.

---

## Status

- [ ] Split views.py into modules
- [x] Remove legacy tests.py file
- [x] Fix CutomSetPasswordForm typo
- [ ] Remove print() statements
- [ ] Fix empty signal handler
- [ ] Restrict ALLOWED_HOSTS in production
- [ ] Optimize UserLastRequestMiddleware
- [ ] Move image processing to Celery
- [ ] Add Redis caching for like counts
- [ ] Extract Redis client to service layer
- [x] Remove django-debug-toolbar
