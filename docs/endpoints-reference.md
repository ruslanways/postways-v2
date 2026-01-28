# Complete API Endpoints Reference

This document provides a comprehensive list of all endpoints in the Postways application, including HTTP methods, paths, request bodies, and authentication requirements.

---

## Table of Contents

1. [API Endpoints (`/api/v1/`)](#api-endpoints-apiv1)
   - [API Root](#api-root)
   - [Authentication](#authentication)
   - [Users](#users)
   - [Posts](#posts)
   - [Likes](#likes)
2. [HTML Endpoints](#html-endpoints)
   - [Home](#home)
   - [Authentication](#authentication-html)
   - [Authors](#authors)
   - [Posts](#posts-html)

---

## API Endpoints (`/api/v1/`)

All API endpoints use JWT authentication (except where noted). Include the access token in the `Authorization` header:
```
Authorization: Bearer <access_token>
```

### API Root

#### `GET /api/v1/`
- **Authentication**: Not required
- **Request Body**: None
- **Response**: Returns hyperlinks to main API endpoints
- **Example Response**:
  ```json
  {
    "posts": "http://host/api/v1/posts/",
    "users": "http://host/api/v1/users/",
    "likes": "http://host/api/v1/likes/"
  }
  ```

---

### Authentication

#### `POST /api/v1/auth/login/`
- **Authentication**: Not required (this is the login endpoint)
- **Request Body**:
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
- **Response**: Returns both access and refresh tokens
  ```json
  {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
  ```

#### `POST /api/v1/auth/mylogin/`
- **Authentication**: Not required (this is the login endpoint)
- **Request Body**:
  ```json
  {
    "username": "string",
    "password": "string"
  }
  ```
- **Response**: Returns access token in body, sets refresh token as HTTP-only cookie
  ```json
  {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
  ```
- **Note**: Refresh token is set as `refresh_token` cookie with `HttpOnly`, `SameSite=Strict`, and `Secure` (in production)

#### `POST /api/v1/auth/token/refresh/`
- **Authentication**: Not required (uses refresh token)
- **Request Body**:
  ```json
  {
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
  ```
  OR refresh token can be sent as `refresh_token` cookie (for custom login flow)
- **Response**: Returns new access token (and new refresh token if rotation enabled)
  ```json
  {
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."  // Only if ROTATE_REFRESH_TOKENS=True
  }
  ```
- **Note**: Old refresh token is blacklisted if `BLACKLIST_AFTER_ROTATION=True`

#### `POST /api/v1/auth/token/verify/`
- **Authentication**: Not required (this verifies tokens)
- **Request Body**:
  ```json
  {
    "token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
  ```
- **Response**: `200 OK` if valid, `401 Unauthorized` if invalid

#### `POST /api/v1/auth/token/recovery/`
- **Authentication**: Not required
- **Request Body**:
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response**: 
  ```json
  {
    "Recovery email send": "Success"
  }
  ```
- **Note**: 
  - Blacklists all existing refresh tokens for the user
  - Generates new token pair and emails the access token via Celery task
  - User can use the access token to reset password via `POST /api/v1/auth/password/reset/`

#### `POST /api/v1/auth/password/change/`
- **Authentication**: Required
- **Request Body**:
  ```json
  {
    "old_password": "current_password",
    "new_password": "new_secure_password",
    "new_password2": "new_secure_password"
  }
  ```
- **Response**:
  ```json
  {
    "detail": "Password changed successfully."
  }
  ```
- **Note**:
  - Requires verification of the current password before allowing changes
  - New password is validated against Django's password validators
  - **Security**: Logs out from ALL devices after successful change:
    - All JWT refresh tokens are blacklisted (forces API re-authentication)
    - All sessions are invalidated (forces HTML re-login)

#### `POST /api/v1/auth/password/reset/`
- **Authentication**: Required (uses recovery token from email)
- **Request Body**:
  ```json
  {
    "new_password": "new_secure_password",
    "new_password2": "new_secure_password"
  }
  ```
- **Response**:
  ```json
  {
    "detail": "Password reset successfully."
  }
  ```
- **Note**:
  - This is for users who forgot their password and received a recovery token via `POST /api/v1/auth/token/recovery/`
  - Does NOT require the old password (user forgot it)
  - Requires valid JWT access token from recovery email in `Authorization: Bearer <token>` header
  - New password is validated against Django's password validators
  - **Security**: Logs out from ALL devices after successful reset:
    - All JWT refresh tokens are blacklisted (forces API re-authentication)
    - All sessions are invalidated (forces HTML re-login)
  - **Flow**:
    1. User requests recovery via `POST /api/v1/auth/token/recovery/`
    2. User receives email with access token
    3. User calls this endpoint with the token in Authorization header
    4. Password is reset and all sessions/tokens are invalidated

#### `POST /api/v1/auth/username/change/`
- **Authentication**: Required
- **Request Body**:
  ```json
  {
    "password": "current_password",
    "new_username": "new_username"
  }
  ```
- **Response**:
  ```json
  {
    "detail": "Username changed successfully.",
    "username": "new_username"
  }
  ```
- **Note**:
  - Requires verification of the current password before allowing changes
  - New username is validated for:
    - Case-insensitive uniqueness (cannot use existing username in any case variation)
    - Format rules (letters, numbers, and @/./+/-/_ characters only)
  - **Rate Limiting**: Users can only change their username once every 30 days
  - Returns `400 Bad Request` if cooldown period has not passed

#### `POST /api/v1/auth/email/change/`
- **Authentication**: Required
- **Request Body**:
  ```json
  {
    "password": "current_password",
    "new_email": "new@example.com"
  }
  ```
- **Response**:
  ```json
  {
    "detail": "Verification email sent to your new email address."
  }
  ```
- **Note**:
  - Requires verification of the current password before allowing changes
  - New email is validated for:
    - Case-insensitive uniqueness (cannot use existing email in any case variation)
    - Must be different from current email
  - Sends a verification email to the new address with a link that expires in 24 hours
  - Email is NOT updated immediately - user must click the verification link

#### `POST /api/v1/auth/email/verify/` or `GET /api/v1/auth/email/verify/?token=<token>`
- **Authentication**: Not required
- **Request Body** (POST):
  ```json
  {
    "token": "uuid-verification-token"
  }
  ```
- **Query Parameters** (GET):
  - `token=<uuid>` - Verification token from email link
- **Response**:
  ```json
  {
    "detail": "Email changed successfully.",
    "email": "new@example.com"
  }
  ```
- **Note**:
  - Validates that the token exists and is not expired (24-hour validity)
  - Updates user's email to the pending email address
  - Clears pending email fields after successful verification
  - Returns `400 Bad Request` if token is invalid or expired

---

### Users

#### `GET /api/v1/users/`
- **Authentication**: Required (Staff only)
- **Request Body**: None
- **Query Parameters**: Standard pagination (page, page_size)
- **Response**: Paginated list of users, ordered by `last_request` descending
- **Example Response**:
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
        "last_request": "2024-01-15T10:00:00Z",
        "last_login": "2024-01-15T09:00:00Z",
        "date_joined": "2024-01-01T00:00:00Z",
        "is_staff": false,
        "is_active": true
      }
    ]
  }
  ```

#### `POST /api/v1/users/`
- **Authentication**: Not required (registration endpoint - anonymous only)
- **Request Body**:
  ```json
  {
    "username": "string",
    "email": "string",
    "password": "string",
    "password2": "string"
  }
  ```
- **Response**: `201 Created` with user data (passwords excluded)
- **Note**: 
  - Both `password` and `password2` must match
  - Password is validated against Django's password validators
  - Email must be unique

#### `GET /api/v1/users/<id>/`
- **Authentication**: Required (Owner or Admin only)
- **Request Body**: None
- **Response**: User details with posts and likes (all fields are read-only)
- **Example Response**:
  ```json
  {
    "url": "http://host/api/v1/users/1/",
    "id": 1,
    "username": "user1",
    "email": "user1@example.com",
    "last_request": "2024-01-15T10:00:00Z",
    "last_login": "2024-01-15T09:00:00Z",
    "date_joined": "2024-01-01T00:00:00Z",
    "is_staff": false,
    "is_active": true,
    "posts": [
      "http://host/api/v1/posts/1/",
      "http://host/api/v1/posts/2/"
    ],
    "likes": [
      "http://host/api/v1/likes/5/",
      "http://host/api/v1/likes/6/"
    ]
  }
  ```
- **Note**: All user profile fields are read-only. Use dedicated endpoints for changes:
  - Password: `POST /api/v1/auth/password/change/`
  - Username: `POST /api/v1/auth/username/change/`
  - Email: `POST /api/v1/auth/email/change/`

#### `DELETE /api/v1/users/<id>/`
- **Authentication**: Required (Owner or Admin only)
- **Request Body**: None
- **Response**: `204 No Content`
- **Notes**:
  - Blacklists all outstanding refresh tokens for the user before deletion
  - Deleting the user cascades to their posts and likes (via `on_delete=models.CASCADE`)

---

### Posts

#### `GET /api/v1/posts/`
- **Authentication**: Not required (read-only)
- **Request Body**: None
- **Query Parameters**:
  - `author=<user_id>` - Filter by author ID
  - `created__gte=2024-01-01` - Posts created on or after date
  - `created__lte=2024-12-31` - Posts created on or before date
  - `created__date__range=2024-01-01,2024-12-31` - Posts created within date range
  - `updated__gte=2024-01-01` - Posts updated on or after date
  - `updated__lte=2024-12-31` - Posts updated on or before date
  - `ordering=id` or `ordering=updated` or `ordering=created` - Order results
  - Standard pagination: `page`, `page_size`
- **Response**: Paginated list of published posts with like counts
- **Example Response**:
  ```json
  {
    "count": 20,
    "next": "http://host/api/v1/posts/?page=2",
    "previous": null,
    "results": [
      {
        "id": 1,
        "url": "http://host/api/v1/posts/1/",
        "author": "http://host/api/v1/users/2/",
        "title": "My First Post",
        "content": "Post content...",
        "image": "http://host/media/diary/images/post.jpg",
        "created": "2024-01-15T10:00:00Z",
        "updated": "2024-01-15T10:00:00Z",
        "published": true,
        "like_count": 5
      }
    ]
  }
  ```

#### `POST /api/v1/posts/`
- **Authentication**: Required
- **Request Body** (multipart/form-data for image upload):
  ```json
  {
    "title": "string",           // required
    "content": "string",         // required
    "image": "file",             // optional
    "published": true            // optional, defaults to true
  }
  ```
- **Response**: `201 Created` with post data
- **Note**: 
  - Author is automatically set to current user
  - Image processing (resize, thumbnail, EXIF fix) runs asynchronously via Celery
  - Content is validated for profanity

#### `GET /api/v1/posts/<id>/`
- **Authentication**: Not required (for published posts)
- **Request Body**: None
- **Response**: Post details with all likes
- **Example Response**:
  ```json
  {
    "id": 1,
    "url": "http://host/api/v1/posts/1/",
    "author": "http://host/api/v1/users/2/",
    "title": "My First Post",
    "content": "Post content...",
    "image": "http://host/media/diary/images/post.jpg",
    "created": "2024-01-15T10:00:00Z",
    "updated": "2024-01-15T10:00:00Z",
    "published": true,
    "likes": [
      "http://host/api/v1/likes/1/",
      "http://host/api/v1/likes/2/"
    ]
  }
  ```
- **Note**: 
  - Published posts: anyone can view
  - Unpublished posts: owner or admin only (returns `403 Forbidden` otherwise)

#### `PUT /api/v1/posts/<id>/` or `PATCH /api/v1/posts/<id>/`
- **Authentication**: Required (Owner only)
- **Request Body** (all fields optional for PATCH):
  ```json
  {
    "title": "string",           // optional
    "content": "string",         // optional
    "image": "file",             // optional
    "published": true            // optional
  }
  ```
- **Response**: `200 OK` with updated post data
- **Note**: 
  - Author cannot be changed
  - Image processing runs if image is updated

#### `DELETE /api/v1/posts/<id>/`
- **Authentication**: Required (Owner or Admin only)
- **Request Body**: None
- **Response**: `204 No Content`
- **Note**: CASCADE deletes all associated likes

---

### Likes

#### `GET /api/v1/likes/`
- **Authentication**: Not required
- **Request Body**: None
- **Query Parameters**:
  - `created__gte=2024-01-01` - Likes created on or after date
  - `created__lte=2024-12-31` - Likes created on or before date
  - `created__date__range=2024-01-01,2024-12-31` - Likes created within date range
  - `ordering=created` or `ordering=likes` - Order results
  - Standard pagination: `page`, `page_size`
- **Response**: Analytics data - daily like counts aggregated by date
- **Example Response**:
  ```json
  {
    "count": 10,
    "next": null,
    "previous": null,
    "results": [
      {
        "created__date": "2024-01-15",
        "likes": 12
      },
      {
        "created__date": "2024-01-14",
        "likes": 8
      }
    ]
  }
  ```

#### `GET /api/v1/likes/<id>/`
- **Authentication**: Not required
- **Request Body**: None
- **Response**: Single like details
- **Example Response**:
  ```json
  {
    "url": "http://host/api/v1/likes/1/",
    "id": 1,
    "created": "2024-01-15T10:00:00Z",
    "user": "http://host/api/v1/users/2/",
    "post": "http://host/api/v1/posts/1/"
  }
  ```

#### `POST /api/v1/likes/toggle/`
- **Authentication**: Required
- **Request Body**:
  ```json
  {
    "post": 1  // post ID (integer)
  }
  ```
- **Response**: 
  - `201 Created` if like was added (includes like data)
  - `204 No Content` if like was removed
- **Note**: 
  - Toggles like status (creates if not exists, deletes if exists)
  - Uses atomic transactions with `select_for_update()` for concurrency safety
  - Broadcasts like count updates via WebSocket to all connected clients
  - Cannot like unpublished posts (returns validation error)

#### `GET /api/v1/likes/batch/`
- **Authentication**: Not required (but authenticated users get `liked` status)
- **Request Body**: None
- **Query Parameters**:
  - `ids=1,2,3` - Comma-separated list of post IDs
- **Response**: Like counts and liked status for requested posts
- **Example Response**:
  ```json
  {
    "1": {
      "count": 5,
      "liked": true
    },
    "2": {
      "count": 3,
      "liked": false
    }
  }
  ```
- **Note**: 
  - Returns empty object `{}` if no IDs provided
  - Returns `400 Bad Request` if IDs are not valid integers
  - Used by frontend to refresh like data after browser back/forward navigation

---

## HTML Endpoints

HTML endpoints use session-based authentication. Users must be logged in via `/login/` to access protected endpoints.

### Home

#### `GET /`
- **Authentication**: Not required
- **Purpose**: Public homepage displaying published posts
- **Query Parameters**: Standard pagination (`page`)
- **Response**: HTML page with paginated posts ordered by most recently updated

#### `GET /popular/`
- **Authentication**: Not required
- **Purpose**: Alternative homepage with posts ordered by most liked
- **Query Parameters**: Standard pagination (`page`)
- **Response**: HTML page with paginated posts ordered by like count

---

### Authentication (HTML)

#### `GET /signup/`
- **Authentication**: Not required
- **Purpose**: Display registration form
- **Response**: HTML registration form

#### `POST /signup/`
- **Authentication**: Not required
- **Purpose**: Create new user account
- **Request Body** (form data):
  ```
  username: string
  email: string
  password: string
  password2: string
  ```
- **Response**: 
  - Success: Auto-logs in user and redirects to `/author/<pk>/` (profile page)
  - Failure: Returns form with validation errors

#### `GET /login/`
- **Authentication**: Not required
- **Purpose**: Display login form
- **Response**: HTML login form

#### `POST /login/`
- **Authentication**: Not required
- **Purpose**: Authenticate user and create session
- **Request Body** (form data):
  ```
  username: string
  password: string
  ```
- **Response**: 
  - Success: Creates session and redirects to `/author/<pk>/` (profile page)
  - Failure: Returns form with error message

#### `GET /logout/` or `POST /logout/`
- **Authentication**: Required (session)
- **Purpose**: Destroy user session
- **Response**: Redirects to `/` (homepage)

#### `GET /password_reset/`
- **Authentication**: Not required
- **Purpose**: Display password reset request form
- **Response**: HTML password reset form

#### `POST /password_reset/`
- **Authentication**: Not required
- **Purpose**: Send password reset email
- **Request Body** (form data):
  ```
  email: string
  ```
- **Response**: 
  - Success: Redirects to `/password_reset/done/`
  - Failure: Returns form with error

#### `GET /reset/<uidb64>/<token>/`
- **Authentication**: Not required
- **Purpose**: Display password reset confirmation form
- **Response**: HTML password reset confirmation form

#### `POST /reset/<uidb64>/<token>/`
- **Authentication**: Not required
- **Purpose**: Reset password with token
- **Request Body** (form data):
  ```
  new_password1: string
  new_password2: string
  ```
- **Response**: 
  - Success: Redirects to `/password_reset/complete/`
  - Failure: Returns form with validation errors

#### `GET /password_change/`
- **Authentication**: Required (session)
- **Purpose**: Display password change form
- **Response**: HTML password change form

#### `POST /password_change/`
- **Authentication**: Required (session)
- **Purpose**: Change password for logged-in user
- **Request Body** (form data):
  ```
  old_password: string
  new_password1: string
  new_password2: string
  ```
- **Response**:
  - Success: Redirects to `/password_change/done/`
  - Failure: Returns form with validation errors
- **Security**: All JWT tokens are blacklisted after successful change (consistent with API behavior)

#### `GET /username_change/`
- **Authentication**: Required (session)
- **Purpose**: Display username change form
- **Response**: HTML username change form

#### `POST /username_change/`
- **Authentication**: Required (session)
- **Purpose**: Change username for logged-in user
- **Request Body** (form data):
  ```
  password: string
  new_username: string
  ```
- **Response**:
  - Success: Redirects to `/author/<pk>/` (profile page) with success message
  - Failure: Returns form with validation errors
- **Note**:
  - Requires current password verification
  - Username must be unique (case-insensitive)
  - 30-day cooldown between username changes

#### `GET /email_change/`
- **Authentication**: Required (session)
- **Purpose**: Display email change form
- **Response**: HTML email change form

#### `POST /email_change/`
- **Authentication**: Required (session)
- **Purpose**: Initiate email change for logged-in user
- **Request Body** (form data):
  ```
  password: string
  new_email: string
  ```
- **Response**:
  - Success: Sends verification email and redirects to `/author/<pk>/` (profile page) with success message
  - Failure: Returns form with validation errors
- **Note**:
  - Requires current password verification
  - New email must be unique (case-insensitive)
  - New email must be different from current email
  - Email is NOT updated immediately - user must click the verification link

#### `GET /email_verify/<token>/`
- **Authentication**: Not required
- **Purpose**: Verify email change and complete the update
- **Response**:
  - Success: Updates email and redirects to `/` (homepage) with success message
  - Invalid/Expired Token: Redirects to `/` (homepage) with error message
- **Note**:
  - Token is valid for 24 hours
  - After verification, pending email fields are cleared

---

### Authors

#### `GET /authors/`
- **Authentication**: Required (Staff only)
- **Purpose**: List all users
- **Query Parameters**: 
  - `sortfield=<field>` - Sort by field (e.g., `username`, `email`)
  - Standard pagination (`page`)
- **Response**: HTML page with paginated user list

#### `GET /authors/<sortfield>/`
- **Authentication**: Required (Staff only)
- **Purpose**: List all users sorted by specified field
- **Response**: HTML page with paginated user list

#### `GET /author/<pk>/`
- **Authentication**: Required (Owner or Admin only)
- **Purpose**: Display user profile with their posts
- **Query Parameters**: Standard pagination (`page`)
- **Response**: HTML profile page with user details and paginated posts list

#### `GET /author/<pk>/delete/`
- **Authentication**: Required (Owner only)
- **Purpose**: Display account deletion confirmation page for the logged-in user
- **Response**: HTML confirmation page with warning about permanent data loss

#### `POST /author/<pk>/delete/`
- **Authentication**: Required (Owner only)
- **Purpose**: Delete the logged-in user's account
- **Request Body**: None (confirmation handled by form)
- **Response**:
  - Success: Blacklists all JWT tokens, logs the user out, deletes the account, and redirects to `/` (homepage)
  - Failure: Redirects to homepage with warning message
- **Notes**:
  - Blacklists all outstanding JWT refresh tokens for the user before deletion (consistent with API behavior)
  - Deleting the account cascades to all of the user's posts and likes

---

### Posts (HTML)

#### `GET /posts/`
- **Authentication**: Not required
- **Purpose**: List all published posts
- **Query Parameters**: Standard pagination (`page`)
- **Response**: HTML page with paginated posts list

#### `GET /posts/add/`
- **Authentication**: Required
- **Purpose**: Display post creation form
- **Response**: HTML post creation form

#### `POST /posts/add/`
- **Authentication**: Required
- **Purpose**: Create new post
- **Request Body** (multipart/form-data):
  ```
  title: string
  content: string
  image: file (optional)
  ```
- **Response**: 
  - Success: Redirects to `/` (homepage)
  - Failure: Returns form with validation errors
- **Note**: 
  - Author is automatically set to current user
  - Image processing runs asynchronously via Celery
  - Content is validated for profanity

#### `GET /posts/<pk>/`
- **Authentication**: Not required (for published posts)
- **Purpose**: Display post details
- **Response**: HTML post detail page
- **Note**: 
  - Published posts: anyone can view
  - Unpublished posts: owner or admin only (returns `403 Forbidden` otherwise)

#### `GET /posts/<pk>/update/`
- **Authentication**: Required (Owner or Staff only)
- **Purpose**: Display post update form
- **Response**: HTML post update form with existing data

#### `POST /posts/<pk>/update/`
- **Authentication**: Required (Owner or Staff only)
- **Purpose**: Update post
- **Request Body** (multipart/form-data):
  ```
  title: string (optional)
  content: string (optional)
  image: file (optional)
  ```
- **Response**: 
  - Success: Redirects to `/posts/<pk>/` (post detail page)
  - Failure: Returns form with validation errors
- **Note**: Image processing runs if image is updated

#### `GET /posts/<pk>/delete/`
- **Authentication**: Required (Owner or Staff only)
- **Purpose**: Display post deletion confirmation page
- **Response**: HTML confirmation page

#### `POST /posts/<pk>/delete/`
- **Authentication**: Required (Owner or Staff only)
- **Purpose**: Delete post
- **Request Body**: None (confirmation handled in form)
- **Response**: 
  - Success: Redirects to `/author/<pk>/` (author's profile page)
  - Failure: Returns confirmation page
- **Note**: CASCADE deletes all associated likes

---

## WebSocket Endpoint

#### `WS /ws/socket-server/` or `WSS /ws/socket-server/`
- **Authentication**: Optional (session or JWT)
- **Purpose**: Real-time like count updates
- **Connection**: 
  - Client connects to WebSocket endpoint
  - Automatically added to "likes" channel group
- **Messages Received**:
  ```json
  {
    "type": "like.message",
    "post_id": "1",
    "like_count": "5",
    "user_id": 2
  }
  ```
- **Note**: 
  - Used for broadcasting like count updates when users like/unlike posts
  - Original user who triggered the like doesn't receive their own broadcast (deduplication)
  - All other connected users receive real-time updates

---

## Authentication Summary

### API Endpoints (JWT)

| Endpoint | Method | Auth Required | Notes |
|----------|--------|---------------|-------|
| `/api/v1/` | GET | No | Public |
| `/api/v1/auth/login/` | POST | No | Login endpoint |
| `/api/v1/auth/mylogin/` | POST | No | Custom login (cookie-based refresh) |
| `/api/v1/auth/token/refresh/` | POST | No | Uses refresh token |
| `/api/v1/auth/token/verify/` | POST | No | Token verification |
| `/api/v1/auth/token/recovery/` | POST | No | Password recovery |
| `/api/v1/auth/password/change/` | POST | Yes | Change password (requires current password) |
| `/api/v1/auth/password/reset/` | POST | Yes* | Reset password (uses recovery token, no old password) |
| `/api/v1/auth/username/change/` | POST | Yes | Change username (requires password, 30-day cooldown) |
| `/api/v1/auth/email/change/` | POST | Yes | Initiate email change (requires password, sends verification) |
| `/api/v1/auth/email/verify/` | POST/GET | No | Verify email change token |
| `/api/v1/users/` | GET | Yes (Staff) | List users |
| `/api/v1/users/` | POST | No | Registration (anonymous only) |
| `/api/v1/users/<id>/` | GET | Yes (Owner/Admin) | User details (read-only) |
| `/api/v1/users/<id>/` | DELETE | Yes (Owner/Admin) | Delete user (blacklists tokens, cascades posts/likes) |
| `/api/v1/posts/` | GET | No | List published posts |
| `/api/v1/posts/` | POST | Yes | Create post |
| `/api/v1/posts/<id>/` | GET | No* | Post details |
| `/api/v1/posts/<id>/` | PUT/PATCH | Yes (Owner) | Update post |
| `/api/v1/posts/<id>/` | DELETE | Yes (Owner/Admin) | Delete post |
| `/api/v1/likes/` | GET | No | Analytics |
| `/api/v1/likes/<id>/` | GET | No | Like details |
| `/api/v1/likes/toggle/` | POST | Yes | Toggle like |
| `/api/v1/likes/batch/` | GET | No | Batch like counts |

*Unpublished posts require owner/admin access

### HTML Endpoints (Session)

| Endpoint | Method | Auth Required | Notes |
|----------|--------|---------------|-------|
| `/` | GET | No | Public homepage |
| `/popular/` | GET | No | Homepage (liked ordering) |
| `/signup/` | GET/POST | No | Registration |
| `/login/` | GET/POST | No | Login |
| `/logout/` | GET/POST | Yes | Logout |
| `/password_reset/` | GET/POST | No | Password reset request |
| `/reset/<uidb64>/<token>/` | GET/POST | No | Password reset confirm |
| `/password_change/` | GET/POST | Yes | Change password (blacklists JWT tokens) |
| `/username_change/` | GET/POST | Yes | Change username (requires password, 30-day cooldown) |
| `/email_change/` | GET/POST | Yes | Initiate email change (requires password, sends verification) |
| `/email_verify/<token>/` | GET | No | Verify email change token |
| `/authors/` | GET | Yes (Staff) | List users |
| `/author/<pk>/` | GET | Yes (Owner/Admin) | User profile |
| `/author/<pk>/delete/` | GET/POST | Yes (Owner) | Delete own account |
| `/posts/` | GET | No | List posts |
| `/posts/add/` | GET/POST | Yes | Create post |
| `/posts/<pk>/` | GET | No* | Post details |
| `/posts/<pk>/update/` | GET/POST | Yes (Owner/Staff) | Update post |
| `/posts/<pk>/delete/` | GET/POST | Yes (Owner/Staff) | Delete post |

*Unpublished posts require owner/admin access

---

## Notes

1. **JWT Token Format**: Include in `Authorization` header as `Bearer <access_token>`
2. **Session Authentication**: HTML endpoints use Django session cookies
3. **Token Expiration**: Access tokens typically expire after 5 minutes (configurable)
4. **Token Rotation**: Refresh tokens are rotated and old ones blacklisted when `ROTATE_REFRESH_TOKENS=True`
5. **Custom Token Refresh**: Uses `MyTokenRefreshSerializer` which fixes a SimpleJWT limitation - the default serializer doesn't track rotated tokens in `OutstandingToken` table, breaking blacklist functionality
6. **Token Blacklisting**: The `blacklist_user_tokens()` utility function blacklists all outstanding tokens for a user, used during account deletion and password recovery
7. **Image Upload**: Use `multipart/form-data` content type for endpoints that accept images
8. **Pagination**: Most list endpoints support standard DRF pagination (`page`, `page_size`)
9. **Filtering**: Post list endpoint supports extensive filtering by author and date ranges
10. **Real-time Updates**: Like count updates are broadcast via WebSocket to all connected clients
11. **Error Responses**: Custom error handlers return JSON for API requests (`/api/*`) and HTML templates for browser requests (400, 403, 404, 500)
