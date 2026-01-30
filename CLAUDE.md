# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Postways is a Django-based diary/blog application with both traditional HTML views and a REST API. It features user authentication (session + JWT), post management with image processing, likes with real-time WebSocket updates, and background task processing.

## Development Commands

```bash
# Start all services (web, db, redis, celery worker, celery beat)
docker compose -f docker/docker-compose.yml up

# First-time setup (after containers are running)
mkdir -p logs

# Run Django management commands inside the container
docker compose -f docker/docker-compose.yml exec web python manage.py <command>

# Apply migrations
docker compose -f docker/docker-compose.yml exec web python manage.py migrate

# Generate demo data
docker compose -f docker/docker-compose.yml exec web python manage.py seed_demo_data

# Create superuser
docker compose -f docker/docker-compose.yml exec web python manage.py createsuperuser

# Run tests (see Testing section below for more options)
docker compose -f docker/docker-compose.yml exec web pytest

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
  - `views/` - Views package (separated for clean code organization)
    - `html.py` - Traditional Django CBVs with session auth (HomeView, SignUp, PostCreateView, UsernameChangeView, EmailChangeView, EmailVerifyView, etc.)
    - `api.py` - DRF views with JWT auth (UserListAPIView, PostAPIView, LikeCreateDestroyAPIView, EmailChangeAPIView, EmailVerifyAPIView, etc.)
    - `__init__.py` - Re-exports all views for backward-compatible imports
- `docker/` - Dockerfile and docker-compose.yml

### Key Components

**Models** (`apps/diary/models.py`):
- `CustomUser` - Extended user model with `last_activity_at` tracking, `username_last_changed` for rate-limiting username changes, and email verification fields (`pending_email`, `email_verification_token`, `email_verification_expires`). Related names: `user.posts` (all posts), `user.likes` (all likes given)
- `Post` - Blog posts with `created_at`/`updated_at` timestamps and async image processing via Celery (resizing, thumbnail generation, EXIF orientation fix). Also handles media cleanup when images are cleared or replaced during edit (queues deletion via Celery). Related names: `post.author` (author user), `post.likes` (all likes on post)
- `Like` - Post likes with `created_at` timestamp and unique constraint per user/post. Related names: `like.user`, `like.post`

**Signals** (`apps/diary/signals.py`):
- `log_user_login` - Logs user login events for monitoring/audit
- `queue_post_image_deletion` - Queues async deletion of post images (image + thumbnail) when a post is deleted. Uses `pre_delete` signal to capture file paths before deletion, then `transaction.on_commit()` to ensure the Celery task only runs if the deletion succeeds. Works with both local storage and S3.

**Authentication**:
- Session-based for HTML views
- JWT (SimpleJWT) for API with token rotation and blacklisting
- Custom token recovery via email
 - Account deletion flows (both use `blacklist_user_tokens()` utility function for consistency):
   - API: `UserDetailAPIView.destroy()` uses atomic transaction to blacklist all tokens and delete user (cascades posts/likes)
   - HTML: `UserDeleteView` requires login, provides an owner-only confirmation page, blacklists JWT tokens, logs out, then deletes account

**API** (`apps/diary/views/api.py`):
- REST endpoints under `/api/v1/`
- Custom permissions: `OwnerOrAdmin`, `OwnerOrAdminOrReadOnly`, `ReadForAdminCreateForAnonymous`

**JWT Authentication Details** (`apps/diary/views/api.py`):

The project uses SimpleJWT with custom enhancements for secure token management:

| Component | Location | Purpose |
|-----------|----------|---------|
| `blacklist_user_tokens()` | `api.py` | Utility to blacklist all outstanding refresh tokens for a user |
| `broadcast_like_update()` | `api.py` | Utility to broadcast like count updates via WebSocket |
| `MyTokenObtainPairView` | `api.py` | Custom login with httponly cookie for refresh token |
| `MyTokenRefreshSerializer` | `serializers.py` | Fixes OutstandingToken tracking for rotated tokens |
| `MyTokenRefreshView` | `api.py` | Uses custom serializer for proper blacklist support |
| `TokenRecoveryAPIView` | `api.py` | Password recovery: blacklists tokens, emails access token for reset |
| `PasswordResetAPIView` | `api.py` | Reset password using recovery token (no old password required) |
| `PasswordChangeAPIView` | `api.py` | Secure password change requiring current password |
| `UsernameChangeAPIView` | `api.py` | Secure username change with password verification and 30-day cooldown |
| `EmailChangeAPIView` | `api.py` | Initiate email change with password verification and verification email |
| `EmailVerifyAPIView` | `api.py` | Verify email change token and complete email update |

**Key Implementation Details:**

1. **Token Blacklisting Utility** (`blacklist_user_tokens()`):
   - Finds all `OutstandingToken` entries for a user
   - Creates `BlacklistedToken` entries for each (with `ignore_conflicts=True`)
   - Used by: account deletion (API + HTML), password recovery, password reset, password change

2. **Custom Token Refresh Serializer** (`MyTokenRefreshSerializer`):
   - **Problem**: Default SimpleJWT `TokenRefreshSerializer` doesn't add rotated refresh tokens to `OutstandingToken` table
   - **Impact**: Without this fix, blacklisting doesn't work for rotated tokens
   - **Solution**: Manually creates `OutstandingToken` record after generating new refresh token
   - Includes: JTI, expiration time, user reference, and token string

3. **Secure Cookie Login** (`MyTokenObtainPairView`):
   - Returns access token in response body (for JS storage in memory)
   - Sets refresh token as HTTP-only cookie with:
     - `httponly=True` - prevents XSS attacks
     - `samesite="Strict"` - prevents CSRF attacks
     - `secure=not settings.DEBUG` - HTTPS-only in production

**Custom Error Handlers** (`config/urls.py`, `apps/diary/views/api.py`, `apps/diary/middleware.py`):
- Custom error pages for 400, 403, 404, and 500 errors
- Returns JSON for API requests (`/api/*`), HTML templates for browser requests
- Templates located in `templates/` directory: `400.html`, `403.html`, `404.html`, `500.html`
- 500 errors handled by `UncaughtExceptionMiddleware` with logging support

**WebSocket - Real-time Likes** (`apps/diary/consumers.py`):

The application uses Django Channels to broadcast like count updates in real-time. This means when one user likes a post, all other users viewing that post immediately see the updated like count without refreshing the page.

#### Key Files

| File | Purpose |
|------|---------|
| `config/asgi.py` | Entry point that routes HTTP requests to Django and WebSocket connections to Channels |
| `apps/diary/routing.py` | Defines the WebSocket URL pattern (`ws/socket-server/`) |
| `apps/diary/consumers.py` | The `LikeConsumer` class that handles WebSocket connections |
| `apps/diary/static/diary/fetch.js` | Frontend JavaScript that connects to WebSocket and handles likes |
| `apps/diary/views/api.py` | `LikeCreateDestroyAPIView` that processes likes and triggers broadcasts |
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
→ Calls broadcast_like_update() utility to notify all users
```

**Step 4: Broadcasting to All Users**
```
broadcast_like_update() calls channel_layer.group_send()
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
const isAuthenticated = document.body.dataset.authenticated === "true";
```

When the page loads:
1. Get the CSRF token for making secure requests
2. Find all like buttons on the page (elements with class "like")
3. Extract the post IDs from those elements
4. Check if user is logged in (via `data-authenticated` attribute on `<body>` tag)

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
2. Detect current state via `.is-liked` CSS class (more robust than charCode check)
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

**When it's used:** After back/forward navigation (bfcache restoration) or when tab becomes visible and WebSocket needed reconnection.

**Why it's needed:** When you navigate away and use the browser back button, the page might be restored from cache with stale like counts. This function fetches the current counts and updates the UI.

**How it works:**
1. Sends single request with all post IDs: `GET /api/v1/likes/batch/?ids=1,2,3`
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

// Reconnect and refresh when tab becomes visible again (after being hidden)
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      connectWebSocket();
      refreshLikeCounts();
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
   - Fetch fresh like counts to sync any changes missed while tab was hidden

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
| `delete_media_files` | Deletes media files from storage (local or S3) with retries | On-demand via `pre_delete` signal on `Post` |
| `send_token_recovery_email` | Emails password recovery token | On-demand via `.delay()` |
| `send_email_verification` | Emails verification link for email change | On-demand via `.delay()` |
| `send_week_report` | Emails weekly stats (users, posts, likes) | Scheduled: Saturday 10:00 |

#### Task Invocation

**On-demand task** - called in `apps/diary/views/api.py` (`TokenRecoveryAPIView`):
```python
send_token_recovery_email.delay(password_reset_url, str(refresh.access_token), user.email)
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

## Testing

The project uses **pytest** with pytest-django, pytest-factoryboy, pytest-xdist, and pytest-cov. All test commands run inside the Docker container.

### Basic Test Commands

```bash
# Run all tests
docker compose -f docker/docker-compose.yml exec web pytest

# Run tests with verbose output
docker compose -f docker/docker-compose.yml exec web pytest -v

# Run a specific test file
docker compose -f docker/docker-compose.yml exec web pytest apps/diary/tests/test_user_api.py

# Run a specific test class or function
docker compose -f docker/docker-compose.yml exec web pytest apps/diary/tests/test_user_api.py::TestUserList
docker compose -f docker/docker-compose.yml exec web pytest apps/diary/tests/test_user_api.py::TestUserList::test_list_users_as_admin

# Run tests matching a keyword expression
docker compose -f docker/docker-compose.yml exec web pytest -k "user and not delete"
```

### Parallel Execution (pytest-xdist)

```bash
# Run tests in parallel using all available CPU cores
docker compose -f docker/docker-compose.yml exec web pytest -n auto

# Run tests using a specific number of workers
docker compose -f docker/docker-compose.yml exec web pytest -n 4
```

### Code Coverage (pytest-cov)

```bash
# Run tests with coverage report (terminal output)
docker compose -f docker/docker-compose.yml exec web pytest --cov=apps

# Run tests with coverage and show missing lines
docker compose -f docker/docker-compose.yml exec web pytest --cov=apps --cov-report=term-missing

# Generate HTML coverage report (output to var/coverage/htmlcov/)
docker compose -f docker/docker-compose.yml exec web pytest --cov=apps --cov-report=html

# Combined: parallel + coverage + missing lines
docker compose -f docker/docker-compose.yml exec web pytest -n auto --cov=apps --cov-report=term-missing
```

### Coverage Configuration

Coverage settings are in `pyproject.toml`:
- **Data file**: `var/coverage/.coverage`
- **HTML report**: `var/coverage/htmlcov/`
- **Omitted paths**: migrations, management commands, consumers, routing, tasks, templatetags

### Test Fixtures

Test fixtures are defined in `apps/diary/tests/conftest.py`:

| Fixture | Description |
|---------|-------------|
| `user` | Regular user created via UserFactory |
| `admin_user` | Staff user created via AdminUserFactory |
| `other_user` | Another regular user (for permission tests) |
| `user_client` | Django test client logged in as `user` |
| `api_client` | Unauthenticated DRF APIClient |
| `authenticated_api_client` | APIClient with JWT auth as `user` |
| `admin_api_client` | APIClient with JWT auth as `admin_user` |
| `other_user_api_client` | APIClient with JWT auth as `other_user` |
| `post` | Published post owned by `user` |
| `unpublished_post` | Unpublished post owned by `user` |
| `other_user_post` | Published post owned by `other_user` |
| `like` | Like from `user` on `post` |

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
- Always use Context7 MCP proactively (without being explicitly asked) when working with:
  - Library/API documentation lookup
  - Code generation involving external libraries
  - Setup or configuration steps
  - Framework or library configuration
  - Version-sensitive APIs or behavior
  - Infrastructure, deployment, or lifecycle hooks
- Prefer project context and existing code when refactoring or extending features
- Do not use Context7 for pure business logic, refactors, or exploratory design unless explicitly requested

### Code Quality & Principles
- Follow SOLID and KISS principles pragmatically
- Avoid over-engineering and premature abstraction
- Prioritize readability and long-term maintainability
