# Postways

A Django-based diary/blog application with both traditional HTML views and a REST API. Features user authentication (session + JWT), post management with image processing, likes with real-time WebSocket updates, and background task processing.

## Quick Start

```bash
# Start all services (web, db, redis, celery worker, celery beat)
docker compose -f docker/docker-compose.yml up

# First-time setup (after containers are running)
mkdir -p logs

# Apply migrations
docker compose -f docker/docker-compose.yml exec web python manage.py migrate

# Generate demo data
docker compose -f docker/docker-compose.yml exec web python manage.py seed_demo_data

# Create superuser
docker compose -f docker/docker-compose.yml exec web python manage.py createsuperuser

# Run tests (basic)
docker compose -f docker/docker-compose.yml exec web pytest

# Run tests with coverage and missing lines
docker compose -f docker/docker-compose.yml exec web pytest --cov=apps --cov-report=term-missing

# Run tests in parallel with coverage
docker compose -f docker/docker-compose.yml exec web pytest -n auto --cov=apps --cov-report=term-missing

# Install pre-commit hooks (one-time setup, runs linter/formatter before commits)
pre-commit install
```

## Code Quality

The project uses **ruff** for linting and formatting, enforced via **pre-commit** hooks.

```bash
# Run pre-commit hooks manually
pre-commit run --all-files

# Run ruff directly
ruff check --fix .
ruff format .
```

Pre-commit hooks run automatically on `git commit`. If issues are found:
- **Auto-fixable** (imports, formatting): Files are fixed, re-stage with `git add -u` and commit again
- **Non-fixable** (unused variables): Fix manually, then commit

## Testing

The project uses **pytest** with several plugins for comprehensive testing.

### Quick Reference

| Command | Description |
|---------|-------------|
| `pytest` | Run all tests |
| `pytest -v` | Verbose output |
| `pytest -n auto` | Parallel execution (all CPUs) |
| `pytest -n 4` | Parallel execution (4 workers) |
| `pytest --cov=apps` | With coverage report |
| `pytest --cov=apps --cov-report=term-missing` | Coverage + missing lines |
| `pytest --cov=apps --cov-report=html` | Generate HTML coverage report |
| `pytest -k "keyword"` | Run tests matching keyword |

All commands should be prefixed with:
```bash
docker compose -f docker/docker-compose.yml exec web
```

### Examples

```bash
# Run a specific test file
docker compose -f docker/docker-compose.yml exec web pytest apps/diary/tests/test_user_api.py

# Run a specific test class
docker compose -f docker/docker-compose.yml exec web pytest apps/diary/tests/test_user_api.py::TestUserList

# Run tests matching a pattern
docker compose -f docker/docker-compose.yml exec web pytest -k "user and not delete"

# Full CI-style run: parallel + coverage + missing lines
docker compose -f docker/docker-compose.yml exec web pytest -n auto --cov=apps --cov-report=term-missing

# Generate HTML coverage report (view at var/coverage/htmlcov/index.html)
docker compose -f docker/docker-compose.yml exec web pytest --cov=apps --cov-report=html
```

### Test Configuration

- **Config file**: `pyproject.toml` (pytest and coverage settings)
- **Fixtures**: `apps/diary/tests/conftest.py` (factories and fixtures)
- **Coverage output**: `var/coverage/` (data file and HTML reports)

## HTML Endpoints

Traditional Django views with session-based authentication.

| URL | Access | Description |
|-----|--------|-------------|
| `/` | Public | Home page - lists published posts (most recent first) |
| `/popular/` | Public | Popular posts - lists published posts by like count |
| `/authors/` | Staff | User list with statistics and sortable columns |
| `/authors/<id>/` | Public* | User profile with their posts |
| `/authors/<id>/delete/` | Owner | Delete own account |
| `/posts/` | Staff | All posts (including unpublished) for moderation |
| `/posts/add/` | Authenticated | Create new post |
| `/posts/<id>/` | Public* | View single post |
| `/posts/<id>/edit/` | Owner/Staff | Edit post |
| `/posts/<id>/delete/` | Owner/Staff | Delete post |
| `/signup/` | Anonymous | User registration |
| `/login/` | Anonymous | User login |
| `/logout/` | Authenticated | User logout |
| `/password_change/` | Authenticated | Change password |
| `/password_reset/` | Anonymous | Request password reset |
| `/username_change/` | Authenticated | Change username (30-day cooldown) |
| `/email_change/` | Authenticated | Request email change |
| `/email_verify/<token>/` | Public | Verify email change |

*Unpublished posts and sensitive user fields visible only to owner/staff

## API Endpoints

All API endpoints are under `/api/v1/` and use JWT authentication (except registration and public read endpoints).

### API Root

**`GET /api/v1/`**
- Returns hyperlinks to all API endpoints organized by category (users, auth, posts, likes)
- No authentication required

---

### Authentication Endpoints

**`POST /api/v1/auth/login/`**
- Standard JWT login (SimpleJWT)
- Returns both access and refresh tokens in response body

**`POST /api/v1/auth/mylogin/`**
- Custom JWT login for HTML/JavaScript clients
- Returns access token in response body
- Sets refresh token as HTTP-only cookie (more secure, prevents XSS)

**`POST /api/v1/auth/token/refresh/`**
- Refresh JWT access token using refresh token
- Uses custom serializer that tracks rotated tokens for blacklist support

**`POST /api/v1/auth/token/verify/`**
- Verify if a JWT token is valid
- Standard SimpleJWT endpoint

**`POST /api/v1/auth/token/recovery/`**
- Password recovery via email
- Request body: `{"email": "user@example.com"}`
- Blacklists all existing tokens for the user
- Generates new access token and emails it (via Celery task)
- User can then use the access token to reset password via `/api/v1/auth/password/reset/`

**`POST /api/v1/auth/password/reset/`**
- Reset password using recovery token (no old password required)
- Request body: `{"new_password": "...", "new_password2": "..."}`
- Requires valid JWT access token (from recovery email)
- New password is validated against Django password validators
- **Security**: Logs out from ALL devices after successful reset (JWT tokens blacklisted + sessions invalidated)

**`POST /api/v1/auth/password/change/`**
- Change password for authenticated users
- Request body: `{"old_password": "...", "new_password": "...", "new_password2": "..."}`
- Requires verification of current password
- New password is validated against Django password validators
- **Security**: Logs out from ALL devices after successful change (JWT tokens blacklisted + sessions invalidated)

**`POST /api/v1/auth/username/change/`**
- Change username for authenticated users
- Request body: `{"password": "...", "new_username": "..."}`
- Requires verification of current password
- New username is validated for case-insensitive uniqueness and format
- **Rate Limiting**: Users can only change username once every 30 days

**`POST /api/v1/auth/email/change/`**
- Initiate email change for authenticated users
- Request body: `{"password": "...", "new_email": "..."}`
- Requires verification of current password
- New email is validated for case-insensitive uniqueness
- Sends verification email to the new address (via Celery task)
- Token expires after 24 hours

**`POST /api/v1/auth/email/verify/`** or **`GET /api/v1/auth/email/verify/?token=<token>`**
- Complete email change by verifying the token
- Request body (POST): `{"token": "..."}`
- Query parameter (GET): `?token=<uuid>`
- Updates user's email to the pending email address
- Clears pending email fields after successful verification

---

### User Endpoints

**`GET /api/v1/users/`**
- List all users (admin only)
- Ordered by `last_activity_at` descending

**`POST /api/v1/users/`**
- Create new user (anonymous/registration endpoint)
- No authentication required

**`GET /api/v1/users/me/`**
- Retrieve current authenticated user's profile
- Allows users to discover their own user ID
- Returns same format as user detail endpoint

**`GET /api/v1/users/{user_id_or_username}/`**
- Retrieve user details with their posts and likes
- Accepts numeric ID (e.g., `/users/42/`) or username (e.g., `/users/john_doe/`)
- Authenticated users only
- Sensitive fields (email, last_activity_at, etc.) visible only to owner or admin
- All fields are read-only; use dedicated endpoints for changes:
  - Password: `/api/v1/auth/password/change/`
  - Username: `/api/v1/auth/username/change/`
  - Email: `/api/v1/auth/email/change/`

**`DELETE /api/v1/users/{user_id_or_username}/`**
- Delete user (owner or admin only)
- Before deletion, blacklists all outstanding refresh tokens for that user
- User deletion cascades to their posts and likes (via `on_delete=models.CASCADE`)

---

### Post Endpoints

**`GET /api/v1/posts/`**
- List published posts with like counts
- Supports filtering:
  - `?author=<user_id>` - Filter by author ID
  - `?created__gte=2024-01-01` - Posts created on or after date
  - `?created__lte=2024-12-31` - Posts created on or before date
  - `?created__date__range=2024-01-01,2024-12-31` - Posts created within date range
  - `?updated__gte=2024-01-01` - Posts updated on or after date
  - `?updated__lte=2024-12-31` - Posts updated on or before date
- Supports ordering: `?ordering=id`, `?ordering=updated`, `?ordering=created`
- No authentication required (read-only)

**`POST /api/v1/posts/`**
- Create new post (authenticated users only)
- Author is automatically set to current user

**`GET /api/v1/posts/<id>/`**
- Retrieve post details
- Published posts: anyone can view
- Unpublished posts: owner or admin only (returns 403 otherwise)

**`PUT/PATCH /api/v1/posts/<id>/`**
- Update post (owner only)

**`DELETE /api/v1/posts/<id>/`**
- Delete post (owner or admin only)

---

### Like Endpoints

**`GET /api/v1/likes/`**
- Response format varies based on query parameters:
  - No filters: Returns total like count (`{"total_likes": 42, "results": []}`)
  - `?user={user_id}`: Returns user's likes with post info
  - `?post={post_id}`: Returns post's likes with user info
  - `?user={user_id}&post={post_id}`: Returns boolean (`{"liked": true}`)
- Supports pagination for filtered results

**`GET /api/v1/likes/{id}/`**
- Retrieve a single like by ID with full user and post details

**`POST /api/v1/likes/toggle/`**
- Toggle like on a post (authenticated users only)
- Request body: `{"post": <post_id>}`
- If user hasn't liked → creates like → returns 201
- If user already liked → removes like → returns 204
- Uses atomic transactions with `select_for_update()` for concurrency safety
- Broadcasts like count updates via WebSocket to all connected clients

**`GET /api/v1/likes/batch/`**
- Batch endpoint to get like counts for multiple posts
- Query parameter: `?ids=1,2,3` (comma-separated post IDs)
- Returns: `{"1": {"count": 5, "liked": true}, "2": {"count": 3, "liked": false}}`
- Used by frontend to refresh like data after browser back/forward navigation
- Returns empty object if no IDs provided
- Returns 400 if IDs are not valid integers

---

### API Endpoints Summary

| Endpoint | Method | Auth Required | Purpose |
|----------|--------|---------------|---------|
| `/api/v1/` | GET | No | API root with hyperlinks |
| `/api/v1/auth/login/` | POST | No | Standard JWT login |
| `/api/v1/auth/mylogin/` | POST | No | Custom JWT login (cookie-based refresh) |
| `/api/v1/auth/token/refresh/` | POST | No | Refresh access token |
| `/api/v1/auth/token/verify/` | POST | No | Verify token validity |
| `/api/v1/auth/token/recovery/` | POST | No | Password recovery via email |
| `/api/v1/auth/password/reset/` | POST | Yes* | Reset password (using recovery token) |
| `/api/v1/auth/password/change/` | POST | Yes | Change password (requires current password) |
| `/api/v1/auth/username/change/` | POST | Yes | Change username (30-day cooldown) |
| `/api/v1/auth/email/change/` | POST | Yes | Initiate email change |
| `/api/v1/auth/email/verify/` | POST/GET | No | Verify email change token |
| `/api/v1/users/` | GET | Admin | List users |
| `/api/v1/users/` | POST | No** | Register new user |
| `/api/v1/users/me/` | GET | Yes | Get current user profile |
| `/api/v1/users/{id_or_username}/` | GET | Yes | Get user details |
| `/api/v1/users/{id_or_username}/` | DELETE | Owner/Admin | Delete user |
| `/api/v1/posts/` | GET | No | List published posts |
| `/api/v1/posts/` | POST | Yes | Create post |
| `/api/v1/posts/{id}/` | GET | No*** | Get post details |
| `/api/v1/posts/{id}/` | PUT/PATCH | Owner | Update post |
| `/api/v1/posts/{id}/` | DELETE | Owner/Admin | Delete post |
| `/api/v1/likes/` | GET | No | Like data (varies by filter) |
| `/api/v1/likes/{id}/` | GET | No | Get like details |
| `/api/v1/likes/toggle/` | POST | Yes | Toggle like on post |
| `/api/v1/likes/batch/` | GET | No | Batch get like counts |

*Uses recovery token from email
**Anonymous only (registration)
***Unpublished posts require Owner/Admin

## Authentication Overview

The project uses **dual authentication** - session-based for HTML views and JWT for the REST API.

### 1. User Model

**Custom User Model** (`apps/diary/models.py`):
- Extends Django's `AbstractUser`
- Uses `AUTH_USER_MODEL = "diary.CustomUser"` in settings
- Adds `last_activity_at` timestamp tracking
- Email is unique and required

### 2. HTML Views (Session-Based Authentication)

**Configuration** (`config/settings.py`):
```python
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"  # Note: Login view overrides this to redirect to profile
LOGOUT_REDIRECT_URL = "home"
```

**Authentication Flow**:
- **Sign Up**: `/signup/` → Creates user → Auto-logs in → Redirects to profile
- **Login**: `/login/` → Session created → Redirects to profile (via `get_default_redirect_url()` override)
- **Logout**: `/logout/` → Session destroyed → Redirects to home
- **Password Reset**: Standard Django password reset flow
- **Password Change**: `/password_change/` → Requires current password → Blacklists JWT tokens
- **Username Change**: `/username_change/` → Requires current password → 30-day cooldown between changes
- **Email Change**: `/email_change/` → Requires current password → Sends verification email → `/email_verify/<token>/` completes change

**Views** (`apps/diary/views/html.py`):
- `SignUp` - User registration with auto-login
- `Login` - Session-based login (overrides redirect to profile page)
- `PasswordReset` - Password reset request
- `CustomPasswordChangeView` - Password change with JWT token blacklisting
- `UsernameChangeView` - Username change with password verification and 30-day cooldown
- `EmailChangeView` - Email change with password verification and email verification
- `EmailVerifyView` - Email verification link handler
- Uses Django's `LoginRequiredMixin` and `UserPassesTestMixin` for access control

**Middleware**:
- `AuthenticationMiddleware` - Attaches `request.user` to all requests
- `SessionMiddleware` - Manages session cookies

### 3. API Views (JWT Authentication)

**Configuration** (`config/settings.py`):
```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",  # Fallback for browser-based API access
    ),
}

SIMPLE_JWT = {
    "ROTATE_REFRESH_TOKENS": True,      # New refresh token on each refresh
    "BLACKLIST_AFTER_ROTATION": True,   # Old tokens blacklisted
    # AUTH_HEADER_TYPES defaults to ("Bearer",) - using default
}
```

**JWT Endpoints** (`apps/diary/urls.py`):
- `POST /api/v1/auth/login/` - Standard JWT login (returns both tokens)
- `POST /api/v1/auth/mylogin/` - Custom login (access token in body, refresh token in HTTP-only cookie)
- `POST /api/v1/auth/token/refresh/` - Refresh access token (with rotation)
- `POST /api/v1/auth/token/verify/` - Verify token validity
- `POST /api/v1/auth/token/recovery/` - Password recovery via email
- `POST /api/v1/auth/password/change/` - Change password (requires current password)

**Token Management**:
1. **Token Rotation**: New refresh token issued on each refresh; old one blacklisted
2. **Blacklisting**: Uses `rest_framework_simplejwt.token_blacklist` to invalidate tokens
3. **Custom Recovery**: `TokenRecoveryAPIView` blacklists all user tokens, generates access token, emails it for use with `PasswordResetAPIView`
4. **Password Reset**: `PasswordResetAPIView` allows password reset using recovery token (no old password required)
5. **Password Change**: `PasswordChangeAPIView` requires current password verification, blacklists all tokens after change
6. **Custom Refresh Serializer**: `MyTokenRefreshSerializer` fixes a SimpleJWT limitation where rotated refresh tokens aren't tracked in `OutstandingToken` table, which would break blacklist functionality
7. **Token Blacklist Utility**: `blacklist_user_tokens()` function (in `apps/diary/views/api.py`) blacklists all outstanding tokens for a user - used during account deletion, password recovery, password reset, and password change

**Custom Login View** (`MyTokenObtainPairView`):
- Returns access token in response body (for JavaScript storage)
- Sets refresh token as HTTP-only cookie (prevents XSS theft)
- Cookie is `SameSite=Strict` and `Secure` in production

### 4. Custom Permissions

**Permission Classes** (`apps/diary/permissions.py`):

| Permission | Access Rules | Used For |
|------------|--------------|----------|
| `OwnerOrAdmin` | Object owner or staff only | User detail/update/delete |
| `OwnerOrAdminOrReadOnly` | Read: everyone<br>Write: owner or staff | Post detail/update/delete |
| `ReadForAdminCreateForAnonymous` | POST: anonymous only<br>Other: staff only | User registration endpoint |

### 5. Authentication Flow Examples

**HTML View Flow**:
```
1. User visits protected page (e.g., /posts/add/)
2. LoginRequiredMixin checks request.user.is_authenticated
3. If not authenticated → redirects to /login/
4. User logs in → session created → redirects to profile
5. Subsequent requests include session cookie → authenticated
```

**API Flow**:
```
1. Client sends: POST /api/v1/auth/login/ with credentials
2. Server validates → returns JWT tokens
3. Client includes: Authorization: Bearer <access_token> in headers
4. JWTAuthentication extracts token → validates → sets request.user
5. Permission classes check access → allow/deny request
```

**Token Refresh Flow**:
```
1. Access token expires (typically 5 minutes)
2. Client sends: POST /api/v1/auth/token/refresh/ with refresh token
3. Server validates refresh token → generates NEW access + refresh tokens
4. Old refresh token is blacklisted
5. Client uses new tokens for subsequent requests
```

### 6. Security Features

1. **CSRF Protection**: Enabled for session-based views
2. **Token Blacklisting**: Prevents reuse of revoked tokens
3. **Token Rotation**: Limits impact of token theft
4. **HTTP-only Cookies**: Refresh token stored securely (custom login)
5. **Password Validators**: Django's built-in validators enforced
6. **Custom Recovery**: Secure token recovery via email

### 7. WebSocket Authentication

WebSocket connections use Django Channels' `AuthMiddlewareStack` (`config/asgi.py`):
- Authenticates WebSocket connections using session or JWT
- Allows real-time like updates to authenticated users

## Tech Stack

- **Django 5.2** with Django REST Framework
- **PostgreSQL** (port 5434 on host)
- **Redis** for Channels (WebSocket) and Celery broker
- **Daphne** ASGI server for WebSocket support
- **Celery** for background tasks (worker + beat scheduler)
- **uv** for Python package management

## Features

- User authentication (session-based for HTML views, JWT for API)
- Post management with async image processing (resizing, thumbnails, EXIF orientation fix)
- Automatic media cleanup when posts are deleted or images are cleared/replaced (async via Celery, works with local storage and S3)
- Real-time like updates via WebSocket
- Popular posts view (sorted by like count)
- Staff-only moderation views for users and posts
- Background task processing with Celery
- Secure password change with current password verification
- Secure username change with password verification and 30-day cooldown
- Secure email change with password verification and email verification link
- Custom token recovery via email
- Account deletion for users (HTML profile button and API), with JWT token blacklisting and cascading removal of posts/likes

## Project Structure

- `config/` - Django settings, URLs, ASGI/WSGI, Celery config
- `apps/diary/` - Main application with models, views, API, WebSocket consumers
- `docker/` - Dockerfile and docker-compose.yml

For more detailed documentation, see [CLAUDE.md](CLAUDE.md).
