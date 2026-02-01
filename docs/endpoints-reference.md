# Postways API Reference

Complete reference for all REST API endpoints in the Postways-v2 application.

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
   - [API Root](#api-root)
   - [Auth](#auth)
   - [Users](#users)
   - [Posts](#posts)
   - [Likes](#likes)
4. [WebSocket](#websocket)
5. [Error Handling](#error-handling)
6. [Quick Reference](#quick-reference)

---

## Overview

### Base URL

```
/api/v1/
```

### Authentication Methods

| Method           | Usage                                                                 |
| ---------------- | --------------------------------------------------------------------- |
| JWT Bearer Token | Include in Authorization header: Bearer ACCESS_TOKEN                  |
| HTTP-only Cookie | Refresh token stored as refresh_token cookie (for /auth/mylogin flow) |

### Permission Labels

| Label         | Description                      |
| ------------- | -------------------------------- |
| Anonymous     | No authentication required       |
| Authenticated | Valid JWT access token required  |
| Owner         | Resource belongs to current user |
| Admin         | User has is_staff=True           |
| OwnerOrAdmin  | Owner or staff user              |

### Response Formats

- **Success**: JSON with resource data
- **Error**: JSON with error details (see [Error Handling](#error-handling))
- **Pagination**: List endpoints return `{count, next, previous, results}`

---

## Authentication

All API endpoints use JWT (JSON Web Token) authentication unless otherwise specified.

### Token Lifecycle

1. **Obtain tokens**: `POST /api/v1/auth/login/` or `POST /api/v1/auth/mylogin/`
2. **Use access token**: Include in `Authorization: Bearer <token>` header
3. **Refresh tokens**: `POST /api/v1/auth/token/refresh/` before access token expires
4. **Token rotation**: Old refresh tokens are blacklisted when rotated (configurable)

### Token Configuration

| Setting                  | Default   | Description                       |
| ------------------------ | --------- | --------------------------------- |
| Access token lifetime    | 5 minutes | Short-lived for security          |
| Refresh token lifetime   | 1 day     | Longer-lived, stored securely     |
| Token rotation           | Enabled   | New refresh token on each refresh |
| Blacklist after rotation | Enabled   | Old tokens invalidated            |

---

## API Endpoints

### API Root

#### `GET /api/v1/`

| Method | Permission | Request | Response |
| ------ | ---------- | ------- | -------- |
| GET    | Anonymous  | —       | 200 OK   |

Returns hyperlinks to all API endpoints organized by category.

**Response:**

```json
{
  "users": {
    "list": "http://host/api/v1/users/",
    "me": "http://host/api/v1/users/me/",
    "detail": "http://host/api/v1/users/{user_id_or_username}/"
  },
  "auth": {
    "login": "http://host/api/v1/auth/login/",
    "login_with_cookie": "http://host/api/v1/auth/mylogin/",
    "token_verify": "http://host/api/v1/auth/token/verify/",
    "token_refresh": "http://host/api/v1/auth/token/refresh/",
    "token_recovery": "http://host/api/v1/auth/token/recovery/",
    "password_change": "http://host/api/v1/auth/password/change/",
    "password_reset": "http://host/api/v1/auth/password/reset/",
    "username_change": "http://host/api/v1/auth/username/change/",
    "email_change": "http://host/api/v1/auth/email/change/",
    "email_verify": "http://host/api/v1/auth/email/verify/"
  },
  "posts": {
    "list": "http://host/api/v1/posts/",
    "detail": "http://host/api/v1/posts/{post_id}/"
  },
  "likes": {
    "list": "http://host/api/v1/likes/",
    "detail": "http://host/api/v1/likes/{like_id}/",
    "toggle": "http://host/api/v1/likes/toggle/",
    "batch": "http://host/api/v1/likes/batch/"
  }
}
```

---

### Auth

Authentication endpoints for login, token management, password recovery, and account settings.

#### `POST /api/v1/auth/login/`

| Method | Permission | Request                  | Response           |
| ------ | ---------- | ------------------------ | ------------------ |
| POST   | Anonymous  | JSON: username, password | 200 OK with tokens |

Standard JWT login. Returns both tokens in response body.

**Request:**

```json
{
  "username": "john_doe",
  "password": "secure_password"
}
```

**Response:**

```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

---

#### `POST /api/v1/auth/mylogin/`

| Method | Permission | Request                  | Response                          |
| ------ | ---------- | ------------------------ | --------------------------------- |
| POST   | Anonymous  | JSON: username, password | 200 OK with access token + cookie |

Secure login for browser clients. Returns access token in body, sets refresh token as HTTP-only cookie.

**Request:**

```json
{
  "username": "john_doe",
  "password": "secure_password"
}
```

**Response:**

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Cookie Set:**

| Name          | Value             | Attributes                                    |
| ------------- | ----------------- | --------------------------------------------- |
| refresh_token | JWT refresh token | HttpOnly, SameSite=Strict, Secure (prod only) |

---

#### `POST /api/v1/auth/token/refresh/`

| Method | Permission | Request                 | Response               |
| ------ | ---------- | ----------------------- | ---------------------- |
| POST   | Anonymous  | JSON: refresh or cookie | 200 OK with new tokens |

Refresh access token using refresh token. Accepts token in body or as `refresh_token` cookie.

**Request (body):**

```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response:**

```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Notes:**

- Old refresh token is blacklisted when rotation is enabled
- Uses custom serializer to properly track rotated tokens in OutstandingToken table

---

#### `POST /api/v1/auth/token/verify/`

| Method | Permission | Request     | Response                   |
| ------ | ---------- | ----------- | -------------------------- |
| POST   | Anonymous  | JSON: token | 200 OK or 401 Unauthorized |

Verify if a token is valid.

**Request:**

```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**Response (valid):** `200 OK` with empty body  
**Response (invalid):** `401 Unauthorized`

---

#### `POST /api/v1/auth/token/recovery/`

| Method | Permission | Request     | Response                |
| ------ | ---------- | ----------- | ----------------------- |
| POST   | Anonymous  | JSON: email | 200 OK or 404 Not Found |

Request password recovery. Blacklists all existing tokens and sends recovery email.

**Request:**

```json
{
  "email": "user@example.com"
}
```

**Response (success):**

```json
{
  "Recovery email send": "Success"
}
```

**Response (not found):**

```json
{
  "error": "No user found with this email"
}
```

**Security:**

- All existing refresh tokens are blacklisted
- New access token is generated and emailed (via Celery)
- User can reset password using `POST /api/v1/auth/password/reset/`

---

#### `POST /api/v1/auth/password/change/`

| Method | Permission    | Request                                         | Response |
| ------ | ------------- | ----------------------------------------------- | -------- |
| POST   | Authenticated | JSON: old_password, new_password, new_password2 | 200 OK   |

Change password for authenticated user. Requires current password verification.

**Request:**

```json
{
  "old_password": "current_password",
  "new_password": "new_secure_password",
  "new_password2": "new_secure_password"
}
```

**Response:**

```json
{
  "detail": "Password changed successfully."
}
```

**Security:**

- Requires verification of current password
- New password validated against Django password validators
- **Logs out from ALL devices:**
  - All JWT refresh tokens are blacklisted
  - All sessions are invalidated

---

#### `POST /api/v1/auth/password/reset/`

| Method | Permission      | Request                           | Response |
| ------ | --------------- | --------------------------------- | -------- |
| POST   | Authenticated\* | JSON: new_password, new_password2 | 200 OK   |

Reset password using recovery token. Does NOT require old password.

\*Uses the access token from recovery email.

**Request:**

```json
{
  "new_password": "new_secure_password",
  "new_password2": "new_secure_password"
}
```

**Response:**

```json
{
  "detail": "Password reset successfully."
}
```

**Flow:**

1. User requests recovery via `POST /api/v1/auth/token/recovery/`
2. User receives email with access token
3. User calls this endpoint with token in `Authorization: Bearer <token>` header
4. Password is reset and all sessions/tokens are invalidated

---

#### `POST /api/v1/auth/username/change/`

| Method | Permission    | Request                      | Response |
| ------ | ------------- | ---------------------------- | -------- |
| POST   | Authenticated | JSON: password, new_username | 200 OK   |

Change username for authenticated user. Requires password verification and enforces 30-day cooldown.

**Request:**

```json
{
  "password": "current_password",
  "new_username": "new_username"
}
```

**Response:**

```json
{
  "detail": "Username changed successfully.",
  "username": "new_username"
}
```

**Validation:**

- Password must be correct
- Username must be unique (case-insensitive)
- Username format: letters, numbers, and `@.+-_` characters only
- 30-day cooldown between changes

**Error (cooldown active):**

```json
{
  "new_username": "You can only change your username once every 30 days. Please wait X more day(s)."
}
```

---

#### `POST /api/v1/auth/email/change/`

| Method | Permission    | Request                   | Response |
| ------ | ------------- | ------------------------- | -------- |
| POST   | Authenticated | JSON: password, new_email | 200 OK   |

Initiate email change. Sends verification email to new address.

**Request:**

```json
{
  "password": "current_password",
  "new_email": "new@example.com"
}
```

**Response:**

```json
{
  "detail": "Verification email sent to your new email address."
}
```

**Validation:**

- Password must be correct
- Email must be unique (case-insensitive)
- Email must be different from current email

**Note:** Email is NOT updated immediately. User must click verification link (valid for 24 hours).

---

#### `POST /api/v1/auth/email/verify/` or `GET /api/v1/auth/email/verify/?token=<token>`

| Method | Permission | Request      | Response |
| ------ | ---------- | ------------ | -------- |
| POST   | Anonymous  | JSON: token  | 200 OK   |
| GET    | Anonymous  | Query: token | 200 OK   |

Verify email change token and complete email update.

**Request (POST):**

```json
{
  "token": "uuid-verification-token"
}
```

**Response:**

```json
{
  "detail": "Email changed successfully.",
  "email": "new@example.com"
}
```

**Error (invalid/expired):**

```json
{
  "token": ["Invalid verification token."]
}
```

or

```json
{
  "token": ["Verification token has expired."]
}
```

---

### Users

User management endpoints for registration, profile viewing, and account deletion.

#### `/api/v1/users/`

| Method | Permission  | Request                                    | Response               |
| ------ | ----------- | ------------------------------------------ | ---------------------- |
| GET    | Admin       | Query: page, page_size                     | 200 OK, paginated list |
| POST   | Anonymous\* | JSON: username, email, password, password2 | 201 Created            |

\*POST is for registration only (anonymous users). Authenticated users cannot register.

**GET Response (Admin):**

```json
{
  "count": 10,
  "next": "http://host/api/v1/users/?page=2",
  "previous": null,
  "results": [
    {
      "url": "http://host/api/v1/users/1/",
      "id": 1,
      "username": "user1",
      "email": "user1@example.com",
      "last_activity_at": "2024-01-15T10:00:00Z",
      "last_login": "2024-01-15T09:00:00Z",
      "date_joined": "2024-01-01T00:00:00Z",
      "is_staff": false,
      "is_active": true,
      "stats": {
        "posts_count": 5,
        "likes_received": 42
      }
    }
  ]
}
```

**POST Request (Registration):**

```json
{
  "username": "new_user",
  "email": "user@example.com",
  "password": "secure_password",
  "password2": "secure_password"
}
```

**POST Response:**

Returns user profile format (same as `GET /api/v1/users/{id}/`).

**Validation:**

- `password` and `password2` must match
- Password validated against Django password validators
- Email must be unique

---

#### `GET /api/v1/users/me/`

| Method | Permission    | Request | Response |
| ------ | ------------- | ------- | -------- |
| GET    | Authenticated | —       | 200 OK   |

Retrieve current authenticated user's profile. Allows users to discover their own user ID.

**Response:**

Same as `GET /api/v1/users/{id}/` (all fields visible since user is the owner).

---

#### `/api/v1/users/{user_id_or_username}/`

| Method | Permission    | Request | Response       |
| ------ | ------------- | ------- | -------------- |
| GET    | Authenticated | —       | 200 OK         |
| DELETE | OwnerOrAdmin  | —       | 204 No Content |

The identifier can be a numeric ID (e.g., `/users/42/`) or username (e.g., `/users/john_doe/`).

**GET Response:**

```json
{
  "id": 1,
  "username": "user1",
  "email": "user1@example.com",
  "date_joined": "2024-01-01T00:00:00Z",
  "last_login": "2024-01-15T09:00:00Z",
  "last_activity_at": "2024-01-15T10:00:00Z",
  "is_staff": false,
  "is_active": true,
  "stats": {
    "posts_count": 5,
    "likes_received": 42
  },
  "links": {
    "self": "http://host/api/v1/users/1/",
    "posts": "http://host/api/v1/posts/?author=1"
  }
}
```

**Field Visibility:**

| Field                        | Owner     | Admin     | Other Users    |
| ---------------------------- | --------- | --------- | -------------- |
| id, username, date_joined    | ✓         | ✓         | ✓              |
| email                        | ✓         | ✓         | Hidden         |
| last_activity_at, last_login | ✓         | ✓         | Hidden         |
| is_staff, is_active          | ✓         | ✓         | Hidden         |
| stats.posts_count            | All posts | All posts | Published only |
| stats.likes_received         | All posts | All posts | Published only |

**DELETE Notes:**

- Blacklists all outstanding JWT refresh tokens before deletion
- Cascades to delete all user's posts and likes
- Atomic transaction ensures consistency

**Note:** User profile updates are handled by dedicated endpoints:

- Password: `POST /api/v1/auth/password/change/`
- Username: `POST /api/v1/auth/username/change/`
- Email: `POST /api/v1/auth/email/change/`

---

### Posts

Post management endpoints for creating, reading, updating, and deleting blog posts.

#### `/api/v1/posts/`

| Method | Permission    | Request                                               | Response               |
| ------ | ------------- | ----------------------------------------------------- | ---------------------- |
| GET    | Anonymous     | Query params (see below)                              | 200 OK, paginated list |
| POST   | Authenticated | multipart/form-data: title, content, image, published | 201 Created            |

**GET Query Parameters:**

| Parameter               | Description                                                         |
| ----------------------- | ------------------------------------------------------------------- |
| author                  | Filter by author ID                                                 |
| author\_\_username      | Filter by author username (exact or icontains)                      |
| created_at\_\_gte       | Posts created on or after date                                      |
| created_at\_\_lte       | Posts created on or before date                                     |
| created_at**date**range | Posts created within date range (e.g., 2024-01-01,2024-12-31)       |
| updated_at\_\_gte       | Posts updated on or after date                                      |
| updated_at\_\_lte       | Posts updated on or before date                                     |
| ordering                | Order by: id, -id, created_at, -created_at, updated_at, -updated_at |
| search                  | Search in title and content                                         |
| page, page_size         | Pagination                                                          |

**GET Response:**

```json
{
  "count": 20,
  "next": "http://host/api/v1/posts/?page=2",
  "previous": null,
  "results": [
    {
      "url": "http://host/api/v1/posts/1/",
      "id": 1,
      "author": {
        "id": 2,
        "username": "john_doe",
        "url": "http://host/api/v1/users/2/"
      },
      "title": "My First Post",
      "content_excerpt": "Post content truncated to 200 chars...",
      "thumbnail": "http://host/media/diary/thumbnails/post_thumb.jpg",
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-15T10:00:00Z",
      "likes": "http://host/api/v1/likes/?post=1",
      "stats": {
        "like_count": 5,
        "has_liked": true
      }
    }
  ]
}
```

**Notes:**

- `stats.has_liked` only included for authenticated users (otherwise omitted)
- List only shows published posts
- Default ordering: `-updated_at`, `-id` (for stable pagination)

**POST Request:**

```
Content-Type: multipart/form-data

title: My New Post
content: This is the post content...
image: (binary file, optional)
published: true (optional, defaults to true)
```

**POST Response:**

```json
{
  "url": "http://host/api/v1/posts/1/",
  "id": 1,
  "author": "http://host/api/v1/users/2/",
  "title": "My New Post",
  "content": "This is the post content...",
  "image": "http://host/media/diary/images/post.jpg",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z",
  "likes": "http://host/api/v1/likes/?post=1"
}
```

**POST Notes:**

- Author is automatically set to current user
- Content is validated for profanity
- Image processing (resize, thumbnail, EXIF fix) runs asynchronously via Celery

---

#### `/api/v1/posts/{id}/`

| Method | Permission   | Request                                               | Response       |
| ------ | ------------ | ----------------------------------------------------- | -------------- |
| GET    | Anonymous\*  | —                                                     | 200 OK         |
| PUT    | Owner        | multipart/form-data: title, content, image, published | 200 OK         |
| PATCH  | Owner        | multipart/form-data: partial fields                   | 200 OK         |
| DELETE | OwnerOrAdmin | —                                                     | 204 No Content |

\*Unpublished posts: 403 Forbidden unless owner or admin.

**GET Response:**

```json
{
  "url": "http://host/api/v1/posts/1/",
  "id": 1,
  "author": {
    "id": 2,
    "username": "john_doe",
    "url": "http://host/api/v1/users/2/"
  },
  "title": "My First Post",
  "content": "Full post content...",
  "image": "http://host/media/diary/images/post.jpg",
  "thumbnail": "http://host/media/diary/thumbnails/post_thumb.jpg",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z",
  "published": true,
  "likes": "http://host/api/v1/likes/?post=1",
  "stats": {
    "likes_count": 5,
    "has_liked": true
  }
}
```

**Field Visibility:**

| Field           | Owner | Admin | Other Users        |
| --------------- | ----- | ----- | ------------------ |
| All fields      | ✓     | ✓     | ✓                  |
| published       | ✓     | ✓     | Hidden             |
| stats.has_liked | ✓     | ✓     | Authenticated only |

**PUT/PATCH Notes:**

- Author cannot be changed
- Image processing runs if image is updated
- For PATCH, only provided fields are updated

**DELETE Notes:**

- Cascades to delete all associated likes
- Media files (image + thumbnail) are deleted asynchronously via Celery

---

### Likes

Like management endpoints for toggling likes, viewing like analytics, and batch operations.

#### `GET /api/v1/likes/`

| Method | Permission | Request                  | Response         |
| ------ | ---------- | ------------------------ | ---------------- |
| GET    | Anonymous  | Query params (see below) | Varies by filter |

Response format depends on query parameters:

**1. No filters → Total count:**

```
GET /api/v1/likes/
```

```json
{
  "total_likes": 42,
  "results": []
}
```

**2. Filter by user → User's likes with post info:**

```
GET /api/v1/likes/?user={user_id}
```

```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "url": "http://host/api/v1/likes/1/",
      "id": 1,
      "created_at": "2024-01-15T10:00:00Z",
      "post": {
        "id": 5,
        "title": "Post title (truncated to 50 chars)...",
        "url": "http://host/api/v1/posts/5/"
      }
    }
  ]
}
```

**3. Filter by post → Post's likes with user info:**

```
GET /api/v1/likes/?post={post_id}
```

```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "url": "http://host/api/v1/likes/1/",
      "id": 1,
      "created_at": "2024-01-15T10:00:00Z",
      "user": {
        "id": 2,
        "username": "john_doe",
        "url": "http://host/api/v1/users/2/"
      }
    }
  ]
}
```

**4. Filter by both → Boolean check:**

```
GET /api/v1/likes/?user={user_id}&post={post_id}
```

```json
{
  "liked": true
}
```

---

#### `GET /api/v1/likes/{id}/`

| Method | Permission | Request | Response |
| ------ | ---------- | ------- | -------- |
| GET    | Anonymous  | —       | 200 OK   |

Retrieve a single like with full user and post details.

**Response:**

```json
{
  "url": "http://host/api/v1/likes/1/",
  "id": 1,
  "created_at": "2024-01-15T10:00:00Z",
  "user": {
    "id": 2,
    "username": "john_doe",
    "url": "http://host/api/v1/users/2/"
  },
  "post": {
    "id": 5,
    "title": "Post title (truncated to 50 chars)...",
    "url": "http://host/api/v1/posts/5/"
  }
}
```

---

#### `POST /api/v1/likes/toggle/`

| Method | Permission    | Request         | Response                      |
| ------ | ------------- | --------------- | ----------------------------- |
| POST   | Authenticated | JSON: post (ID) | 201 Created or 204 No Content |

Toggle like status on a post. Creates like if not exists, removes if exists.

**Request:**

```json
{
  "post": 1
}
```

**Response (like created):** `201 Created`

```json
{
  "url": "http://host/api/v1/likes/1/",
  "id": 1,
  "created_at": "2024-01-15T10:00:00Z",
  "user": "http://host/api/v1/users/2/",
  "post": "http://host/api/v1/posts/1/"
}
```

**Response (like removed):** `204 No Content`

**Validation:**

- Cannot like unpublished posts

**Implementation Details:**

- Uses atomic transaction with `select_for_update()` for concurrency safety
- Handles race conditions gracefully
- Broadcasts like count update via WebSocket to all connected clients

---

#### `GET /api/v1/likes/batch/`

| Method | Permission | Request                               | Response |
| ------ | ---------- | ------------------------------------- | -------- |
| GET    | Anonymous  | Query: ids (comma-separated post IDs) | 200 OK   |

Batch endpoint to get like counts for multiple posts in a single request.

**Request:**

```
GET /api/v1/likes/batch/?ids=1,2,3
```

**Response:**

```json
{
  "1": {
    "count": 5,
    "liked": true
  },
  "2": {
    "count": 3,
    "liked": false
  },
  "3": {
    "count": 0,
    "liked": false
  }
}
```

**Notes:**

- `liked` field reflects current user's like status (authenticated users only)
- Returns empty object `{}` if no IDs provided
- Returns `400 Bad Request` if IDs are not valid integers
- Used by frontend to refresh like data after browser back/forward navigation

---

## WebSocket

Real-time like count updates via WebSocket.

#### `WS /ws/socket-server/` or `WSS /ws/socket-server/`

| Protocol  | Authentication | Purpose                      |
| --------- | -------------- | ---------------------------- |
| WebSocket | Optional       | Real-time like count updates |

**Connection:**

- Client connects to WebSocket endpoint
- Automatically added to "likes" channel group
- Receives broadcasts when any user likes/unlikes a post

**Message Format (received):**

```json
{
  "type": "like.message",
  "post_id": "1",
  "like_count": "5",
  "user_id": 2
}
```

**Behavior:**

- User who triggered the like does NOT receive their own broadcast (deduplication via `user_id`)
- All other connected users receive real-time updates
- Works for both authenticated and anonymous users (anonymous can view, not like)

---

## Error Handling

### Error Response Format

API errors return JSON:

```json
{
  "error": "Error message"
}
```

or for validation errors:

```json
{
  "field_name": ["Error message 1", "Error message 2"]
}
```

### HTTP Status Codes

| Code | Meaning                                          |
| ---- | ------------------------------------------------ |
| 200  | OK - Request succeeded                           |
| 201  | Created - Resource created                       |
| 204  | No Content - Request succeeded, no body returned |
| 400  | Bad Request - Invalid input, validation error    |
| 401  | Unauthorized - Authentication required or failed |
| 403  | Forbidden - Authenticated but not authorized     |
| 404  | Not Found - Resource doesn't exist               |
| 500  | Internal Server Error - Server error             |

### Custom Error Pages

| Path        | Format                                                 |
| ----------- | ------------------------------------------------------ |
| /api/\*     | JSON response                                          |
| Other paths | HTML template (400.html, 403.html, 404.html, 500.html) |

---

## Quick Reference

### All API Endpoints

| Endpoint                      | Method    | Permission      | Description                       |
| ----------------------------- | --------- | --------------- | --------------------------------- |
| /api/v1/                      | GET       | Anonymous       | API root with hyperlinks          |
| /api/v1/auth/login/           | POST      | Anonymous       | Standard JWT login                |
| /api/v1/auth/mylogin/         | POST      | Anonymous       | Cookie-based JWT login            |
| /api/v1/auth/token/refresh/   | POST      | Anonymous       | Refresh access token              |
| /api/v1/auth/token/verify/    | POST      | Anonymous       | Verify token validity             |
| /api/v1/auth/token/recovery/  | POST      | Anonymous       | Request password recovery         |
| /api/v1/auth/password/change/ | POST      | Authenticated   | Change password                   |
| /api/v1/auth/password/reset/  | POST      | Authenticated\* | Reset password (via recovery)     |
| /api/v1/auth/username/change/ | POST      | Authenticated   | Change username (30-day cooldown) |
| /api/v1/auth/email/change/    | POST      | Authenticated   | Initiate email change             |
| /api/v1/auth/email/verify/    | POST/GET  | Anonymous       | Verify email change token         |
| /api/v1/users/                | GET       | Admin           | List all users                    |
| /api/v1/users/                | POST      | Anonymous\*\*   | Register new user                 |
| /api/v1/users/me/             | GET       | Authenticated   | Get current user profile          |
| /api/v1/users/{id}/           | GET       | Authenticated   | Get user profile                  |
| /api/v1/users/{id}/           | DELETE    | OwnerOrAdmin    | Delete user account               |
| /api/v1/posts/                | GET       | Anonymous       | List published posts              |
| /api/v1/posts/                | POST      | Authenticated   | Create new post                   |
| /api/v1/posts/{id}/           | GET       | Anonymous\*\*\* | Get post details                  |
| /api/v1/posts/{id}/           | PUT/PATCH | Owner           | Update post                       |
| /api/v1/posts/{id}/           | DELETE    | OwnerOrAdmin    | Delete post                       |
| /api/v1/likes/                | GET       | Anonymous       | Like analytics (varies by filter) |
| /api/v1/likes/{id}/           | GET       | Anonymous       | Get single like details           |
| /api/v1/likes/toggle/         | POST      | Authenticated   | Toggle like on post               |
| /api/v1/likes/batch/          | GET       | Anonymous       | Batch like counts                 |

\*Uses recovery token from email  
**Anonymous only (registration)  
\***Unpublished posts require OwnerOrAdmin

### Permission Classes

| Class                              | Usage                                                    |
| ---------------------------------- | -------------------------------------------------------- |
| ReadForAdminCreateForAnonymous     | User list/create: Admin reads, anonymous creates         |
| AuthenticatedReadOwnerOrAdminWrite | User detail: Authenticated reads, OwnerOrAdmin writes    |
| OwnerOrAdminOrReadOnly             | Posts: Anyone reads, Owner updates, OwnerOrAdmin deletes |
| IsAuthenticated                    | Likes toggle, password/username/email change             |
| IsAuthenticatedOrReadOnly          | Post list/create: Anyone reads, authenticated creates    |
