# Plan: Post View Counts with Redis + PostgreSQL

## Context

The project has no view counting. This feature adds it using a **write-through buffering** pattern: Redis handles high-frequency increments (one `INCR` per page view), and a Celery beat task flushes accumulated counts to PostgreSQL every 5 minutes. This gives the user hands-on experience with Redis as a NoSQL data store beyond its current role as a message broker/cache.

**Redis DB allocation after this change:**
- DB 0: Channels (WebSocket)
- DB 1: Celery broker/result backend
- DB 2: Django cache
- DB 3: View counters (new)

---

## Step 1: Add `view_count` field to Post model

**File:** `apps/diary/models.py` (after the `published` field)

Add:
```python
view_count = models.PositiveIntegerField(
    default=0,
    help_text="Total number of views (periodically synced from Redis).",
)
```

Then generate migration via `makemigrations`.

---

## Step 2: Add Redis DB setting

**File:** `config/settings.py` (after `REDIS_PORT`)

Add:
```python
REDIS_VIEW_COUNT_DB = 3
```

---

## Step 3: Create Redis view-counting service

**New file:** `apps/diary/services.py`

Three functions over a lazy-initialized `redis.Redis(db=3, decode_responses=True)` client:

1. **`record_view(post_id, request)`**
   - Dedup key: `post:viewed:{post_id}:u:{user.pk}` (authenticated) or `post:viewed:{post_id}:a:{md5(ip+ua)[:12]}` (anonymous)
   - `SET <dedup_key> 1 NX EX 300` — if returns True (new viewer), `INCR post:views:{post_id}`
   - Wrapped in try/except `redis.RedisError` → log warning, don't crash

2. **`get_view_count_from_redis(post_id)`**
   - `GET post:views:{post_id}` → int or 0
   - Used by detail views for real-time total

3. **`get_and_clear_all_view_counts()`**
   - `SCAN` with `post:views:*` pattern, `GETDEL` each key (atomic read+delete, Redis 6.2+)
   - Returns `{post_id: increment}` dict
   - Used by the Celery flush task

---

## Step 4: Add Celery flush task

**File:** `apps/diary/tasks.py` — add new task:

```python
@shared_task
def flush_view_counts():
    from apps.diary.services import get_and_clear_all_view_counts
    from apps.diary.models import Post
    from django.db import models as db_models

    counts = get_and_clear_all_view_counts()
    for post_id, increment in counts.items():
        Post.objects.filter(pk=post_id).update(
            view_count=db_models.F("view_count") + increment
        )
```

Follows existing pattern: `filter(pk=...).update()` with `F()` for atomic SQL update.

---

## Step 5: Register in Celery beat schedule

**File:** `config/celery.py` — add to `app.conf.beat_schedule` dict:

```python
"flush-view-counts": {
    "task": "apps.diary.tasks.flush_view_counts",
    "schedule": 300.0,  # Every 5 minutes
    "options": {"expires": 300},
},
```

---

## Step 6: Increment views in HTML PostDetailView

**File:** `apps/diary/views/html.py` — modify `PostDetailView.get()`

After the unpublished-post check, before building context:
```python
record_view(self.object.pk, request)
self.object.total_view_count = (
    self.object.view_count + get_view_count_from_redis(self.object.pk)
)
```

Import `record_view` and `get_view_count_from_redis` from `apps.diary.services`.

---

## Step 7: Increment views in API PostDetailAPIView

**File:** `apps/diary/views/api.py` — modify `PostDetailAPIView.retrieve()`

After the unpublished-post check, before serializing:
```python
record_view(instance.pk, request)
instance.total_view_count = (
    instance.view_count + get_view_count_from_redis(instance.pk)
)
```

---

## Step 8: Update serializers

**File:** `apps/diary/serializers.py`

**PostListSerializer.get_stats()** — add `view_count` from DB field (no Redis read for lists):
```python
stats = {
    "like_count": getattr(obj, "like_count", 0),
    "view_count": obj.view_count,
}
```

**PostDetailSerializer.get_stats()** — add real-time total:
```python
stats = {
    "likes_count": getattr(obj, "likes_count", obj.likes.count()),
    "view_count": getattr(obj, "total_view_count", obj.view_count),
}
```

---

## Step 9: Update templates

**`apps/diary/templates/diary/post_detail.html`** (in `post-detail-meta` div, before the like section):
```html
<span class="post-card-views">👁 {{ object.total_view_count }}</span>
```

**`apps/diary/templates/diary/_post_card.html`** (in `post-card-meta` div, after the date span):
```html
<span class="post-card-views">👁 {{ post.view_count }}</span>
```

List views use the DB-only `view_count` (slightly stale). Detail view uses `total_view_count` (real-time = DB + Redis).

---

## Step 10: Write tests

**New file:** `apps/diary/tests/test_view_counts.py`

Redis 7 is available in both Docker dev and CI (GitHub Actions service container).

Tests:
1. `record_view` increments Redis counter for a post
2. Dedup: same user viewing same post twice within 5 min → counter increments only once
3. Different users → counter increments for each
4. `flush_view_counts` task: sets Redis counters → runs task → verifies DB `view_count` updated, Redis keys cleared
5. `flush_view_counts` with `F()` atomicity: DB starts at 5, Redis has 3 → DB becomes 8
6. HTML detail view: GET returns 200, response context has `total_view_count`
7. API detail view: GET response includes `view_count` in stats
8. Graceful degradation: mock Redis as unavailable → views still return 200

Add a `redis_client` fixture in conftest that connects to DB 3 and flushes it in teardown.

---

## Files changed

| File | Type | Description |
|------|------|-------------|
| `apps/diary/models.py` | Modify | Add `view_count` field |
| `apps/diary/migrations/0006_*.py` | New (auto) | Migration |
| `apps/diary/services.py` | **New** | Redis view counting service |
| `apps/diary/tasks.py` | Modify | Add `flush_view_counts` task |
| `config/celery.py` | Modify | Add beat schedule entry |
| `config/settings.py` | Modify | Add `REDIS_VIEW_COUNT_DB = 3` |
| `apps/diary/views/html.py` | Modify | Record view + attach total in `PostDetailView.get()` |
| `apps/diary/views/api.py` | Modify | Record view + attach total in `PostDetailAPIView.retrieve()` |
| `apps/diary/serializers.py` | Modify | Add `view_count` to stats in both serializers |
| `apps/diary/templates/diary/post_detail.html` | Modify | Display real-time view count |
| `apps/diary/templates/diary/_post_card.html` | Modify | Display DB view count |
| `apps/diary/tests/test_view_counts.py` | **New** | Tests for view counting |
| `apps/diary/tests/conftest.py` | Modify | Add `redis_client` fixture |

---

## Verification

1. **Migration**: `docker compose -f docker/docker-compose.dev.yml exec web python manage.py migrate`
2. **Manual test**: Open a post detail page → check Redis DB 3 for `post:views:{id}` key → wait 5 min (or manually run `flush_view_counts` task) → verify DB `view_count` updated
3. **Dedup test**: Refresh the same post page → verify Redis counter doesn't increment within 5 min
4. **API test**: `GET /api/v1/posts/{id}/` → confirm `view_count` in stats
5. **Run tests**: `docker compose -f docker/docker-compose.dev.yml exec web pytest apps/diary/tests/test_view_counts.py -v`
6. **Run full suite**: `docker compose -f docker/docker-compose.dev.yml exec web pytest`
7. **Lint**: `ruff check . && ruff format .`
