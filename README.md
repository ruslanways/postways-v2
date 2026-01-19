# Postways

A Django-based diary/blog application with both traditional HTML views and a REST API. Features user authentication (session + JWT), post management with image processing, likes with real-time WebSocket updates, and background task processing.

## Quick Start

```bash
# Start all services (web, db, redis, celery worker, celery beat)
docker compose -f docker/docker-compose.yml up

# Apply migrations
docker compose -f docker/docker-compose.yml exec web python manage.py migrate

# Create superuser
docker compose -f docker/docker-compose.yml exec web python manage.py createsuperuser

# Run tests
docker compose -f docker/docker-compose.yml exec web python manage.py test
```

## API Endpoints

All API endpoints are under `/api/v1/` and use JWT authentication (except registration and public read endpoints).

### API Root

**`GET /api/v1/`**
- Returns links to main API endpoints (posts, users, likes)
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
- Generates new token pair and emails the access token (via Celery task)
- User can then use the access token to update password via UserDetailAPIView

---

### User Endpoints

**`GET /api/v1/users/`**
- List all users (admin only)
- Ordered by `last_request` descending

**`POST /api/v1/users/`**
- Create new user (anonymous/registration endpoint)
- No authentication required

**`GET /api/v1/users/<id>/`**
- Retrieve user details with their posts and likes
- Owner or admin only

**`PUT/PATCH /api/v1/users/<id>/`**
- Update user (owner or admin only)

**`DELETE /api/v1/users/<id>/`**
- Delete user (owner or admin only)

---

### Post Endpoints

**`GET /api/v1/posts/`**
- List published posts with like counts
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
- Analytics endpoint: list likes aggregated by date
- Returns daily like counts
- Supports filtering: `?created__gte=2024-01-01&created__lte=2024-12-31`
- Supports ordering: `?ordering=created` or `?ordering=likes`

**`GET /api/v1/likes/<id>/`**
- Retrieve a single like by ID with user and post references

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
| `/api/v1/` | GET | No | API root with links |
| `/api/v1/auth/login/` | POST | No | Standard JWT login |
| `/api/v1/auth/mylogin/` | POST | No | Custom JWT login (cookie-based refresh) |
| `/api/v1/auth/token/refresh/` | POST | No | Refresh access token |
| `/api/v1/auth/token/verify/` | POST | No | Verify token validity |
| `/api/v1/auth/token/recovery/` | POST | No | Password recovery via email |
| `/api/v1/users/` | GET | Admin | List users |
| `/api/v1/users/` | POST | No | Register new user |
| `/api/v1/users/<id>/` | GET | Owner/Admin | Get user details |
| `/api/v1/users/<id>/` | PUT/PATCH | Owner/Admin | Update user |
| `/api/v1/users/<id>/` | DELETE | Owner/Admin | Delete user |
| `/api/v1/posts/` | GET | No | List published posts |
| `/api/v1/posts/` | POST | Yes | Create post |
| `/api/v1/posts/<id>/` | GET | No* | Get post details |
| `/api/v1/posts/<id>/` | PUT/PATCH | Owner | Update post |
| `/api/v1/posts/<id>/` | DELETE | Owner/Admin | Delete post |
| `/api/v1/likes/` | GET | No | Analytics: daily like counts |
| `/api/v1/likes/<id>/` | GET | No | Get like details |
| `/api/v1/likes/toggle/` | POST | Yes | Toggle like on post |
| `/api/v1/likes/batch/` | GET | No | Batch get like counts |

*Unpublished posts require owner/admin access

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
- Real-time like updates via WebSocket
- Background task processing with Celery
- Custom token recovery via email

## Project Structure

- `config/` - Django settings, URLs, ASGI/WSGI, Celery config
- `apps/diary/` - Main application with models, views, API, WebSocket consumers
- `docker/` - Dockerfile and docker-compose.yml

For more detailed documentation, see [CLAUDE.md](CLAUDE.md).
