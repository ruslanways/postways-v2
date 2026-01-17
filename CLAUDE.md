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
- `Post` - Blog posts with automatic image resizing (max 2000x2000) and thumbnail generation (300x300)
- `Like` - Post likes with unique constraint per user/post

**Authentication**:
- Session-based for HTML views
- JWT (SimpleJWT) for API with token rotation and blacklisting
- Custom token recovery via email

**API** (`apps/diary/views.py`, lines 255+):
- REST endpoints under `/api/v1/`
- Custom permissions: `OwnerOrAdmin`, `OwnerOrAdminOrReadOnly`, `ReadForAdminCreateForAnonymous`

**WebSocket - Real-time Likes** (`apps/diary/consumers.py`):

The application uses Django Channels to broadcast like count updates in real-time.

Key files:
- `config/asgi.py` - ASGI routing with `ProtocolTypeRouter` for HTTP and WebSocket
- `apps/diary/routing.py` - WebSocket URL pattern (`ws/socket-server/`)
- `apps/diary/consumers.py` - `LikeConsumer` (AsyncWebsocketConsumer)
- `apps/diary/static/diary/fetch.js` - Frontend WebSocket client
- `config/settings.py` - `CHANNEL_LAYERS` config using Redis

Data flow:
1. User likes/unlikes a post via `LikeCreateDestroyAPIView`
2. View calls `channel_layer.group_send()` to broadcast to the "likes" group
3. `LikeConsumer.like_message()` receives the event and sends JSON to connected clients
4. Frontend updates the like count in the DOM

User behavior:
| User Type     | Can Like | Sees Live Updates | Notes                                    |
|---------------|----------|-------------------|------------------------------------------|
| Authenticated | Yes      | Yes               | Heart color changes optimistically on click |
| Anonymous     | No       | Yes               | Receives all broadcast updates           |

The consumer excludes the user who triggered the like from receiving the broadcast (they update optimistically on the frontend).

**Background Tasks** (`apps/diary/tasks.py`):
- `send_token_recovery_email` - Token recovery emails
- `send_week_report` - Weekly stats email (runs Saturday 10:00 via Celery Beat)

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
