# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Postways is a Django-based diary/blog application with both traditional HTML views and a REST API. It features user authentication (session + JWT), post management with image processing, likes with real-time WebSocket updates, and background task processing.

## Development Commands

```bash
# Start all services (web, db, redis, celery worker, celery beat)
docker compose -f docker/docker-compose.yml up

# Run Django management commands inside the container
docker compose -f docker/docker-compose.yml exec web python manage.py <command>

# Apply migrations
docker compose -f docker/docker-compose.yml exec web python manage.py migrate

# Create superuser
docker compose -f docker/docker-compose.yml exec web python manage.py createsuperuser

# Run tests
docker compose -f docker/docker-compose.yml exec web python manage.py test

# Install dependencies (uses uv)
uv sync
```

## Architecture

### Tech Stack
- **Django 5.2** with Django REST Framework
- **PostgreSQL** (port 5434 on host)
- **Redis** for Channels (WebSocket) and Celery broker
- **Daphne** ASGI server for WebSocket support
- **Celery** for background tasks (worker + beat scheduler)
- **uv** for Python package management

### Project Structure
- `config/` - Django settings, URLs, ASGI/WSGI, Celery config
- `apps/diary/` - Main application with models, views, API, WebSocket consumers
- `docker/` - Dockerfile and docker-compose.yml

### Key Components

**Models** (`apps/diary/models.py`):
- `CustomUser` - Extended user model with `last_request` tracking
- `Post` - Blog posts with async image processing via Celery (resizing, thumbnail generation, EXIF orientation fix)
- `Like` - Post likes with unique constraint per user/post

**Authentication**:
- Session-based for HTML views
- JWT (SimpleJWT) for API with token rotation and blacklisting
- Custom token recovery via email

**API** (`apps/diary/views.py`, lines 255+):
- REST endpoints under `/api/v1/`
- Custom permissions: `OwnerOrAdmin`, `OwnerOrAdminOrReadOnly`, `ReadForAdminCreateForAnonymous`

**WebSocket - Real-time Likes** (`apps/diary/consumers.py`):

The application uses Django Channels to broadcast like count updates in real-time. This means when one user likes a post, all other users viewing that post immediately see the updated like count without refreshing the page.

#### Key Files

| File | Purpose |
|------|---------|
| `config/asgi.py` | Entry point that routes HTTP requests to Django and WebSocket connections to Channels |
| `apps/diary/routing.py` | Defines the WebSocket URL pattern (`ws/socket-server/`) |
| `apps/diary/consumers.py` | The `LikeConsumer` class that handles WebSocket connections |
| `apps/diary/static/diary/fetch.js` | Frontend JavaScript that connects to WebSocket and handles likes |
| `apps/diary/views.py` | `LikeCreateDestroyAPIView` that processes likes and triggers broadcasts |
| `config/settings.py` | `CHANNEL_LAYERS` configuration using Redis as the message broker |

#### How It All Works Together (Step by Step)

**Step 1: Page Load - WebSocket Connection**
```
User opens page → Browser loads fetch.js → JavaScript calls connectWebSocket()
→ Browser connects to ws://host/ws/socket-server/
→ Django Channels receives connection in LikeConsumer.connect()
→ Consumer adds this connection to the "likes" group
→ Connection is now ready to receive messages
```

**Step 2: User Clicks Like Button**
```
User clicks ❤ → fetch.js handleLikeClick() runs
→ UI updates IMMEDIATELY (optimistic update: heart fills, count +1)
→ JavaScript sends POST request to /api/v1/likes/
→ Server still processing... but user already sees the change!
```

**Step 3: Server Processes the Like**
```
LikeCreateDestroyAPIView.create() receives request
→ Checks if user already liked this post (with database lock)
→ If not liked: creates Like record → returns 201
→ If already liked: deletes Like record → returns 204
→ Calls _broadcast_like_update() to notify all users
```

**Step 4: Broadcasting to All Users**
```
_broadcast_like_update() calls channel_layer.group_send()
→ Message goes to Redis (message broker)
→ Redis distributes to all Daphne workers
→ Each LikeConsumer.like_message() receives the message
→ Consumer checks: "Is this the user who clicked?"
   - If YES: skip (they already updated optimistically)
   - If NO: send JSON to their browser
```

**Step 5: Other Users See the Update**
```
Browser receives WebSocket message
→ fetch.js socket.onmessage() parses JSON
→ Finds the post element by ID
→ Updates the like count in the DOM
→ User sees new count without refreshing!
```

#### Visual Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         REAL-TIME LIKES FLOW                            │
└─────────────────────────────────────────────────────────────────────────┘

  USER A (clicks like)                         USER B (viewing same page)
       │                                              │
       │ 1. Click ❤                                   │
       ▼                                              │
  ┌─────────┐                                         │
  │ fetch.js│──2. Optimistic UI update               │
  │         │   (heart fills immediately)            │
  │         │                                         │
  │         │──3. POST /api/v1/likes/ ──────┐        │
  └─────────┘                               │        │
                                            ▼        │
                                    ┌──────────────┐ │
                                    │    Django    │ │
                                    │    Views     │ │
                                    │              │ │
                                    │ 4. Save to DB│ │
                                    │ 5. Broadcast │ │
                                    └──────┬───────┘ │
                                           │         │
                                           ▼         │
                                    ┌──────────────┐ │
                                    │    Redis     │ │
                                    │   (broker)   │ │
                                    └──────┬───────┘ │
                                           │         │
                          ┌────────────────┴─────────┴──────────────┐
                          │                                         │
                          ▼                                         ▼
                   ┌─────────────┐                          ┌─────────────┐
                   │ LikeConsumer│                          │ LikeConsumer│
                   │  (User A)   │                          │  (User B)   │
                   │             │                          │             │
                   │ 6. Skip!    │                          │ 6. Send!    │
                   │ (same user) │                          │             │
                   └─────────────┘                          └──────┬──────┘
                                                                   │
                                                                   ▼
                                                            ┌─────────┐
                                                            │ fetch.js│
                                                            │         │
                                                            │ 7. Update
                                                            │    DOM   │
                                                            └─────────┘
                                                                   │
                                                                   ▼
                                                            User B sees
                                                            new count! ✨
```

#### User Behavior Summary

| User Type     | Can Like | Sees Live Updates | Notes                                    |
|---------------|----------|-------------------|------------------------------------------|
| Authenticated | Yes      | Yes               | Heart color changes optimistically on click |
| Anonymous     | No       | Yes               | Receives all broadcast updates           |

#### Why Optimistic Updates?

When User A clicks like, we update their UI immediately WITHOUT waiting for the server response. This is called "optimistic updating" because we optimistically assume the request will succeed.

**Benefits:**
- App feels instant and responsive
- No loading spinners or delays
- User gets immediate feedback

**Safety net:**
- If the server request fails, fetch.js rolls back the UI to the original state
- The user sees the heart revert and the count go back

---

### Detailed: Frontend JavaScript (`apps/diary/static/diary/fetch.js`)

This file handles all like-related functionality in the browser. Here's what each section does:

#### 1. Utilities Section

```javascript
function getCookie(name) { ... }
```
- Extracts the CSRF token from browser cookies
- Django requires this token for POST requests (security feature)
- Without it, the server would reject our like requests

#### 2. Initialization Section

```javascript
const csrfToken = getCookie("csrftoken");
const likeElements = document.querySelectorAll(".like");
const postIds = Array.from(likeElements).map((el) => el.id);
const isAuthenticated = Boolean(document.getElementById("user"));
```

When the page loads:
1. Get the CSRF token for making secure requests
2. Find all like buttons on the page (elements with class "like")
3. Extract the post IDs from those elements
4. Check if user is logged in (by looking for a "user" element)

```javascript
if (isAuthenticated && likeElements.length) {
  likeElements.forEach((el) => el.addEventListener("click", handleLikeClick));
}
```
- Only attach click handlers if user is authenticated
- Anonymous users can see likes but can't click them

#### 3. WebSocket Section

```javascript
function connectWebSocket(forceReconnect = false) { ... }
```

**What it does:**
1. Checks if there are any posts on the page (no posts = no need for WebSocket)
2. Skips if already connected (unless forced)
3. Closes any existing connection before creating a new one
4. Creates WebSocket connection using `ws://` or `wss://` (secure) protocol
5. Sets up message handler to update like counts when broadcasts arrive

**The message handler:**
```javascript
socket.onmessage = (event) => {
  const { post_id, like_count } = JSON.parse(event.data);
  const countEl = document.getElementById(post_id)?.querySelector(".count");
  if (countEl) {
    countEl.textContent = like_count;
  }
};
```
- Receives JSON with `post_id` and `like_count`
- Finds the post element on the page
- Updates the displayed count

#### 4. Like Click Handler

```javascript
async function handleLikeClick(event) { ... }
```

**Step-by-step flow:**
1. Prevent default link behavior (`event.preventDefault()`)
2. Detect current state: is the heart filled (❤) or empty (♡)?
3. **Optimistic update**: immediately toggle the heart and adjust count
4. Send POST request to server
5. If request fails: roll back to original state

**The optimistic update pattern:**
```javascript
// Save original state (for potential rollback)
const originalHeart = heartEl.textContent;
const originalCount = countEl.textContent;

// Update UI immediately
heartEl.textContent = isLiked ? "♡" : "❤";
countEl.textContent = isLiked ? Number(originalCount) - 1 : Number(originalCount) + 1;

// Then send request...
// If it fails, restore original state
```

#### 5. Refresh Function

```javascript
async function refreshLikeCounts() { ... }
```

**Purpose:** Fetch fresh like data from server for all posts on the page.

**When it's used:** After back/forward navigation (bfcache restoration).

**Why it's needed:** When you navigate away and use the browser back button, the page might be restored from cache with stale like counts. This function fetches the current counts and updates the UI.

**How it works:**
1. Sends single request with all post IDs: `GET /likes_counts/?ids=1,2,3`
2. Server returns counts and liked status for each post
3. Updates both the heart symbol and count for each post

#### 6. Page Lifecycle Handlers

```javascript
// Initial connection
connectWebSocket();

// Handle back/forward navigation
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    connectWebSocket(true);
    refreshLikeCounts();
  }
});

// Handle tab visibility
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      connectWebSocket();
    }
  }
});
```

**Three scenarios handled:**

1. **Initial page load**: Connect to WebSocket immediately

2. **Back/forward navigation** (`pageshow` with `event.persisted`):
   - Browser restored page from bfcache (back-forward cache)
   - WebSocket connection is dead (browser kills them when page is cached)
   - Force reconnect and fetch fresh data

3. **Tab becomes visible** (`visibilitychange`):
   - User switched back to this tab
   - Check if WebSocket is still connected
   - Reconnect if needed (connection might have timed out)

**Celery - Background Tasks**

The application uses Celery for asynchronous task processing with two components:
- **Worker** - executes tasks asynchronously
- **Beat** - schedules periodic tasks

#### Key Files

| File | Purpose |
|------|---------|
| `config/celery.py` | Celery app configuration and beat schedule |
| `apps/diary/tasks.py` | Task definitions |
| `config/settings.py` | Redis broker configuration (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`) |
| `docker/docker-compose.yml` | Worker and beat service definitions |

#### Configuration

**`config/celery.py`** - Main Celery app setup:
```python
app = Celery("postways_celery")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()  # Auto-discovers tasks.py in Django apps
```

**`config/settings.py`** - Redis as broker (uses DB 1, separate from Channels):
```python
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"
```

#### Tasks (`apps/diary/tasks.py`)

| Task | Purpose | Trigger |
|------|---------|---------|
| `process_post_image` | Resizes image (max 2000x2000), generates thumbnail (300x300), fixes EXIF orientation | On-demand via `Post.save()` |
| `send_token_recovery_email` | Emails password recovery token | On-demand via `.delay()` |
| `send_week_report` | Emails weekly stats (users, posts, likes) | Scheduled: Saturday 10:00 |

#### Task Invocation

**On-demand task** - called in `apps/diary/views.py:502`:
```python
send_token_recovery_email.delay(link_to_change_user, str(refresh.access_token), user.email)
```
The `.delay()` method sends the task to the queue for async execution.

**Scheduled task** - defined in `config/celery.py`:
```python
app.conf.beat_schedule = {
    'week-report': {
        'task': 'apps.diary.tasks.send_week_report',
        'schedule': crontab(hour=10, minute=0, day_of_week=6),  # Saturday 10:00
    },
}
```

#### Docker Services

Both Celery components run as separate containers:

- **celery_worker**: `celery -A config worker -l info`
- **celery_beat**: `celery -A config beat -l info`

Both depend on PostgreSQL and Redis being healthy before starting.

### Environment Configuration

Environment variables loaded from `config/.env`:
- `DJANGO_SECRET_KEY`, `DEBUG`, `DATABASE_URL`
- `REDIS_HOST`, `REDIS_PORT`
- Email settings: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, `WEEKLY_RECIPIENTS`

## Interaction Rules

### Interaction Modes
- If the request contains "spec-accurate", prioritize correctness and official documentation
- If the request contains "refactor", prioritize minimal, safe changes using existing patterns
- If the request contains "design", prioritize clarity and simplicity over completeness

### Git Commit Messages
- Generate Git commit messages in Conventional Commits format (type(scope): description)
- Use past tense ("added", "refactored", "fixed", "updated")
- Be specific and concise about what changed

### Best Practices
- Follow best practices and design patterns appropriate to the language, framework, and project
- Prefer idiomatic solutions over clever abstractions

### Communication
- Ask clarifying questions only when requirements materially affect correctness
- Otherwise, make reasonable assumptions and state them explicitly

### Documentation & Research
- Use Context7 MCP tools when working with:
  - Framework or library configuration
  - Version-sensitive APIs or behavior
  - Infrastructure, deployment, or lifecycle hooks
- Prefer project context and existing code when refactoring or extending features
- Do not use Context7 for pure business logic, refactors, or exploratory design unless explicitly requested

### Code Quality & Principles
- Follow SOLID and KISS principles pragmatically
- Avoid over-engineering and premature abstraction
- Prioritize readability and long-term maintainability
