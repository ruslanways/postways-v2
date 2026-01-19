# User Paths & Scenarios Guide

This document outlines all user paths and scenarios in the Postways application, organized by user type, authentication method, and feature area.

---

## User Types

| User Type | Characteristics | Access Level |
|-----------|----------------|--------------|
| **Anonymous** | Not logged in | Public posts (read), registration (create) |
| **Authenticated** | Logged in (regular user) | Own posts (CRUD), all published posts (read), like posts |
| **Staff/Admin** | `is_staff=True` | All users (read), all posts (CRUD), user management |

---

## 1. Registration & Authentication Flows

### 1.1 HTML Registration Flow

```
USER (Anonymous)
 │
 │ 1. Visits /signup/
 ▼
 ┌─────────────────────┐
 │ SignUp View         │
 │ (CreateView)        │
 └──────────┬──────────┘
            │
            │ 2. Submits form with username, email, password, password2
            ▼
 ┌─────────────────────┐
 │ Form Validation     │
 │ - Unique username   │
 │ - Unique email      │
 │ - Passwords match   │
 │ - Password strength │
 └──────────┬──────────┘
            │
            ├─ Invalid → Show errors, return to form
            │
            └─ Valid → 3. Create CustomUser
                        4. Auto-login (login(request, user))
                        5. Redirect to /author/<pk>/ (profile page)
```

**User Experience:**
- User fills out registration form
- On success: Automatically logged in and redirected to profile
- On failure: Form errors displayed, stays on signup page

---

### 1.2 HTML Login Flow

```
USER (Anonymous)
 │
 │ 1. Visits /login/
 ▼
 ┌─────────────────────┐
 │ Login View          │
 │ (LoginView)         │
 └──────────┬──────────┘
            │
            │ 2. Submits username/password
            ▼
 ┌─────────────────────┐
 │ Authentication      │
 │ Django auth.authenticate()
 └──────────┬──────────┘
            │
            ├─ Invalid credentials → Show error, stay on login page
            │
            └─ Valid → 3. Create session (login(request, user))
                        4. Redirect to /author/<pk>/ (profile page)
```

**User Experience:**
- User enters credentials
- On success: Session created, redirected to profile
- On failure: Error message, stays on login page

---

### 1.3 API Registration Flow

```
CLIENT
 │
 │ 1. POST /api/v1/users/
 │    Body: {username, email, password, password2}
 ▼
 ┌─────────────────────────────┐
 │ UserListAPIView.create()    │
 │ Permission: Anonymous only  │
 └──────────────┬──────────────┘
                │
                │ 2. Validate serializer
                ▼
 ┌─────────────────────────────┐
 │ Check permissions:          │
 │ - POST: anonymous only ✅   │
 │ - User must NOT be auth ❌  │
 └──────────────┬──────────────┘
                │
                ├─ Not anonymous → 403 Forbidden
                │
                └─ Anonymous → 3. Create CustomUser
                                4. Hash password
                                5. Return 201 Created with user data
```

**API Example:**
```http
POST /api/v1/users/
Content-Type: application/json

{
  "username": "newuser",
  "email": "user@example.com",
  "password": "securepass123",
  "password2": "securepass123"
}

Response: 201 Created
{
  "url": "http://host/api/v1/users/5/",
  "id": 5,
  "username": "newuser",
  "email": "user@example.com"
}
```

**Endpoint Verification:**
- URL: `POST /api/v1/users/` (defined in `apps/diary/urls.py` line 83, included under `api/v1/` on line 107)
- View: `UserListAPIView` (inherits from `generics.ListCreateAPIView`, provides `create()` method for anonymous users)
- Implemented: ✅ Yes

---

### 1.4 API Login Flow (Standard)

```
CLIENT
 │
 │ 1. POST /api/v1/auth/login/
 │    Body: {username, password}
 ▼
 ┌─────────────────────────────┐
 │ TokenObtainPairView         │
 │ (SimpleJWT)                 │
 └──────────────┬──────────────┘
                │
                │ 2. Validate credentials
                ▼
 ┌─────────────────────────────┐
 │ Check username/password     │
 └──────────────┬──────────────┘
                │
                ├─ Invalid → 401 Unauthorized
                │
                └─ Valid → 3. Generate token pair
                            4. Return 200 OK:
                               {
                                 "access": "eyJ0...",
                                 "refresh": "eyJ1..."
                               }
```

**API Example:**
```http
POST /api/v1/auth/login/
Content-Type: application/json

{
  "username": "testuser",
  "password": "password123"
}

Response: 200 OK
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

---

### 1.5 API Login Flow (Custom - Secure Cookie)

```
CLIENT (Browser/JavaScript)
 │
 │ 1. POST /api/v1/auth/mylogin/
 │    Body: {username, password}
 ▼
 ┌─────────────────────────────┐
 │ MyTokenObtainPairView       │
 │ (Custom login)              │
 └──────────────┬──────────────┘
                │
                │ 2. Validate credentials
                ▼
 ┌─────────────────────────────┐
 │ Generate token pair         │
 └──────────────┬──────────────┘
                │
                │ 3. Return access token in body
                │ 4. Set refresh token as HTTP-only cookie
                ▼
 Response: 200 OK
 Body: {"access_token": "eyJ0..."}
 Cookie: refresh_token=eyJ1...; HttpOnly; SameSite=Strict; Secure
```

**Security Benefits:**
- Refresh token not accessible to JavaScript (prevents XSS theft)
- Access token available for API calls
- Cookie is HttpOnly (browser-only, not readable by JS)

---

### 1.6 Password Recovery Flow (API)

```
USER (Forgot Password)
 │
 │ 1. POST /api/v1/auth/token/recovery/
 │    Body: {email: "user@example.com"}
 ▼
 ┌─────────────────────────────┐
 │ TokenRecoveryAPIView        │
 └──────────────┬──────────────┘
                │
                │ 2. Look up user by email
                ▼
 ┌─────────────────────────────┐
 │ User exists?                │
 └──────────────┬──────────────┘
                │
                ├─ No → 404 Not Found
                │
                └─ Yes → 3. Blacklist ALL existing refresh tokens
                           4. Generate NEW token pair
                           5. Send access token via email (Celery task)
                           6. Return 200 OK
```

**Email Contents:**
```
Subject: Postways token recovery

Here are your new access token expires in 5 min.

'access': eyJ0eXAiOiJKV1QiLCJhbGc...

You can use it to change password by Post-request to: http://host/api/v1/users/<id>/

Therefore you could obtain new tokens pair by logging.
```

**Security Note:**
⚠️ **Important**: This endpoint only requires an email address. Anyone who knows a user's email can trigger password recovery, which will:
- Log out all devices (blacklist all refresh tokens)
- Send a recovery email to that address

This is a common pattern but has security implications. Consider implementing rate limiting or additional verification steps in production.

**User Experience:**
- User requests recovery → All devices logged out (tokens blacklisted)
- Receives email with access token
- Uses access token to make PATCH request to `/api/v1/users/<id>/` with new password
- Then logs in normally with new password to obtain new token pair

---

## 2. Post Management Flows

### 2.1 Create Post (HTML)

```
USER (Authenticated)
 │
 │ 1. Visits /posts/add/
 ▼
 ┌─────────────────────────────┐
 │ PostCreateView              │
 │ (LoginRequiredMixin)        │
 └──────────────┬──────────────┘
                │
                │ 2. Check authentication
                ▼
 ┌─────────────────────────────┐
 │ Authenticated?              │
 └──────────────┬──────────────┘
                │
                ├─ No → Redirect to /login/
                │
                └─ Yes → 3. Show form (title, content, image)
                           4. User submits form
                           5. Validate profanity
                           6. Save Post (author = request.user)
                           7. Trigger Celery task for image processing
                           8. Redirect to / (homepage)
```

**Post Creation:**
- Author automatically set to current user
- Created/updated timestamps set automatically
- Published defaults to True
- Image processing runs asynchronously (resize, thumbnail, EXIF fix)

---

### 2.2 Create Post (API)

```
CLIENT (Authenticated)
 │
 │ 1. POST /api/v1/posts/
 │    Authorization: Bearer <access_token>
 │    Body: {title, content, image?, published?}
 ▼
 ┌─────────────────────────────┐
 │ PostAPIView.create()        │
 │ Permission: IsAuthenticated │
 └──────────────┬──────────────┘
                │
                │ 2. Check authentication
                ▼
 ┌─────────────────────────────┐
 │ Authenticated?              │
 └──────────────┬──────────────┘
                │
                ├─ No → 401 Unauthorized
                │
                └─ Yes → 3. Validate serializer
                           4. perform_create(): author = request.user
                           5. Save Post
                           6. Trigger Celery task for image processing
                           7. Return 201 Created with post data
```

**Endpoint Verification:**
- URL: `POST /api/v1/posts/` (defined in `apps/diary/urls.py` line 92)
- View: `PostAPIView` (inherits from `generics.ListCreateAPIView`, provides `create()` method)
- Implemented: ✅ Yes

---

### 2.3 View Post (HTML)

```
USER (Anonymous or Authenticated)
 │
 │ 1. Visits /posts/<pk>/
 ▼
 ┌─────────────────────────────┐
 │ PostDetailView              │
 │ (Public view)               │
 └──────────────┬──────────────┘
                │
                │ 2. Load post with like count
                │ 3. Check if user liked it (if authenticated)
                ▼
 ┌─────────────────────────────┐
 │ Post.published?             │
 └──────────────┬──────────────┘
                │
                ├─ True → Show post (anyone can view)
                │
                └─ False → Only owner/admin can view (handled in template)
```

**Context Provided:**
- Post details (title, content, author, timestamps, image)
- Like count
- `liked_by_user`: Set containing post ID if user liked it (for heart styling)

---

### 2.4 View Post (API)

```
CLIENT
 │
 │ 1. GET /api/v1/posts/<pk>/
 │    Authorization: Bearer <token>? (optional)
 ▼
 ┌─────────────────────────────┐
 │ PostDetailAPIView.retrieve()│
 │ Permission: Read for all    │
 └──────────────┬──────────────┘
                │
                │ 2. Load post
                ▼
 ┌─────────────────────────────┐
 │ Post.published?             │
 └──────────────┬──────────────┘
                │
                ├─ True → 3. Return 200 OK with post data
                │
                └─ False → 4. Check: owner or admin?
                              ├─ No → 403 Forbidden
                              └─ Yes → 5. Return 200 OK with post data
```

**Response Example:**
```json
{
  "url": "http://host/api/v1/posts/1/",
  "id": 1,
  "title": "My First Post",
  "content": "Post content...",
  "author": "http://host/api/v1/users/2/",
  "image": "http://host/media/diary/images/post.jpg",
  "thumbnail": "http://host/media/diary/images/thumbnails/post.jpg",
  "created": "2024-01-15T10:00:00Z",
  "updated": "2024-01-15T10:00:00Z",
  "published": true,
  "likes": 5
}
```

---

### 2.5 Update Post (HTML)

```
USER (Authenticated - Owner or Staff)
 │
 │ 1. Visits /posts/<pk>/update/
 ▼
 ┌─────────────────────────────┐
 │ PostUpdateView              │
 │ (PostOwnerOrStaffMixin)     │
 └──────────────┬──────────────┘
                │
                │ 2. Check: owner or staff?
                ▼
 ┌─────────────────────────────┐
 │ Permission Check            │
 └──────────────┬──────────────┘
                │
                ├─ No → 403 Forbidden or redirect with message
                │
                └─ Yes → 3. Show form with existing data
                           4. User submits changes
                           5. Validate profanity
                           6. Save updated Post
                           7. Trigger image processing if image changed
                           8. Redirect to post detail page
```

---

### 2.6 Update Post (API)

```
CLIENT (Authenticated - Owner or Staff)
 │
 │ 1. PUT/PATCH /api/v1/posts/<pk>/
 │    Authorization: Bearer <access_token>
 │    Body: {title?, content?, image?, published?}
 ▼
 ┌─────────────────────────────┐
 │ PostDetailAPIView.update()  │
 │ Permission: OwnerOrAdmin... │
 └──────────────┬──────────────┘
                │
                │ 2. Check object permission
                ▼
 ┌─────────────────────────────┐
 │ Is owner or staff?          │
 └──────────────┬──────────────┘
                │
                ├─ No → 403 Forbidden
                │
                └─ Yes → 3. Validate serializer
                           4. Update Post (author cannot be changed)
                           5. Trigger image processing if image changed
                           6. Return 200 OK with updated data
```

**Endpoint Verification:**
- URL: `PUT/PATCH /api/v1/posts/<pk>/` (defined in `apps/diary/urls.py` line 93)
- View: `PostDetailAPIView` (inherits from `generics.RetrieveUpdateDestroyAPIView`, provides `update()` and `partial_update()` methods)
- Implemented: ✅ Yes

---

### 2.7 Delete Post (HTML)

```
USER (Authenticated - Owner or Staff)
 │
 │ 1. Visits /posts/<pk>/delete/
 ▼
 ┌─────────────────────────────┐
 │ PostDeleteView              │
 │ (PostOwnerOrStaffMixin)     │
 └──────────────┬──────────────┘
                │
                │ 2. Check: owner or staff?
                ▼
 ┌─────────────────────────────┐
 │ Permission Check            │
 └──────────────┬──────────────┘
                │
                ├─ No → 403 Forbidden
                │
                └─ Yes → 3. Show confirmation page
                           4. User confirms deletion
                           5. Delete Post (CASCADE deletes all likes)
                           6. Redirect to author's profile page
```

---

### 2.8 Delete Post (API)

```
CLIENT (Authenticated - Owner or Staff)
 │
 │ 1. DELETE /api/v1/posts/<pk>/
 │    Authorization: Bearer <access_token>
 ▼
 ┌─────────────────────────────┐
 │ PostDetailAPIView.destroy() │
 │ Permission: OwnerOrAdmin... │
 └──────────────┬──────────────┘
                │
                │ 2. Check object permission
                ▼
 ┌─────────────────────────────┐
 │ Is owner or staff?          │
 └──────────────┬──────────────┘
                │
                ├─ No → 403 Forbidden
                │
                └─ Yes → 3. Delete Post (CASCADE deletes likes)
                           4. Return 204 No Content
```

---

## 3. User Profile & Management Flows

### 3.1 View Own Profile (HTML)

```
USER (Authenticated)
 │
 │ 1. Visits /author/<pk>/ (where pk = own ID)
 ▼
 ┌─────────────────────────────┐
 │ AuthorDetailView            │
 │ (UserPassesTestMixin)       │
 └──────────────┬──────────────┘
                │
                │ 2. Check: owner or staff?
                ▼
 ┌─────────────────────────────┐
 │ Permission Check            │
 └──────────────┬──────────────┘
                │
                ├─ No → 403 Forbidden
                │
                └─ Yes → 3. Load user + paginated posts
                           4. Get liked posts (if authenticated viewer)
                           5. Show profile page with posts list
```

**Profile Page Shows:**
- User details (username, email)
- Paginated list of user's posts (with like counts)
- Which posts the viewer has liked (heart styling)

---

### 3.2 View User Profile (API)

```
CLIENT (Authenticated - Owner or Staff)
 │
 │ 1. GET /api/v1/users/<pk>/
 │    Authorization: Bearer <access_token>
 ▼
 ┌─────────────────────────────┐
 │ UserDetailAPIView.retrieve()│
 │ Permission: OwnerOrAdmin    │
 └──────────────┬──────────────┘
                │
                │ 2. Check object permission
                ▼
 ┌─────────────────────────────┐
 │ Is owner or staff?          │
 └──────────────┬──────────────┘
                │
                ├─ No → 403 Forbidden
                │
                └─ Yes → 3. Load user with posts and likes
                           4. Return 200 OK with user data
```

**Response Example:**
```json
{
  "url": "http://host/api/v1/users/2/",
  "id": 2,
  "username": "testuser",
  "email": "user@example.com",
  "last_request": "2024-01-15T10:30:00Z",
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

---

### 3.3 Update Own Profile (API)

```
CLIENT (Authenticated - Owner)
 │
 │ 1. PATCH /api/v1/users/<pk>/ (own ID)
 │    Authorization: Bearer <access_token>
 │    Body: {username?, email?, password?}
 ▼
 ┌─────────────────────────────┐
 │ UserDetailAPIView.update()  │
 │ Permission: OwnerOrAdmin    │
 └──────────────┬──────────────┘
                │
                │ 2. Check object permission
                ▼
 ┌─────────────────────────────┐
 │ Is owner or staff?          │
 └──────────────┬──────────────┘
                │
                ├─ No → 403 Forbidden
                │
                └─ Yes → 3. Validate serializer
                           4. If password: hash and save
                           5. Update other fields
                           6. Return 200 OK with updated data
```

**Password Update:**
- Password is automatically hashed by Django
- User must provide current password validation (if implemented)
- After password change, old tokens remain valid (user can change password via recovery if needed)

---

### 3.4 List Users (API - Staff Only)

```
CLIENT (Authenticated - Staff Only)
 │
 │ 1. GET /api/v1/users/
 │    Authorization: Bearer <admin_access_token>
 ▼
 ┌─────────────────────────────┐
 │ UserListAPIView.list()      │
 │ Permission: Staff only      │
 └──────────────┬──────────────┘
                │
                │ 2. Check: is staff?
                ▼
 ┌─────────────────────────────┐
 │ Is staff?                   │
 └──────────────┬──────────────┘
                │
                ├─ No → 403 Forbidden
                │
                └─ Yes → 3. Get all users, ordered by last_request DESC
                           4. Paginate results
                           5. Return 200 OK with paginated user list
```

---

## 4. Like Management Flows

### 4.1 Like Post (HTML - JavaScript)

```
USER (Authenticated)
 │
 │ 1. Views post page (HTML with WebSocket connection)
 │ 2. Clicks ❤ button
 ▼
 ┌─────────────────────────────┐
 │ fetch.js: handleLikeClick() │
 └──────────────┬──────────────┘
                │
                │ 3. Optimistic UI update (heart fills, count +1)
                │ 4. POST /api/v1/likes/toggle/
                │    Authorization: Bearer <access_token>
                │    Body: {post: <post_id>}
                ▼
 ┌─────────────────────────────┐
 │ LikeCreateDestroyAPIView    │
 │ Permission: IsAuthenticated │
 └──────────────┬──────────────┘
                │
                │ 5. Check authentication
                ▼
 ┌─────────────────────────────┐
 │ Authenticated?              │
 └──────────────┬──────────────┘
                │
                ├─ No → 401 Unauthorized → UI rollback
                │
                └─ Yes → 6. Atomic transaction:
                            - Check if like exists (with lock)
                            - If exists: DELETE → 204 No Content
                            - If not: CREATE → 201 Created
                         7. Broadcast like update via WebSocket
                         8. Return response
```

**Real-time Broadcast:**
- After toggling like, server broadcasts update to all connected clients
- Message: `{post_id, like_count, user_id}`
- Other users see updated count instantly (without refresh)
- Original user already sees update (optimistic)

---

### 4.2 Like Post (API)

```
CLIENT (Authenticated)
 │
 │ 1. POST /api/v1/likes/toggle/
 │    Authorization: Bearer <access_token>
 │    Body: {post: <post_id>}
 ▼
 ┌─────────────────────────────┐
 │ LikeCreateDestroyAPIView    │
 │ Permission: IsAuthenticated │
 └──────────────┬──────────────┘
                │
                │ 2. Check authentication
                ▼
 ┌─────────────────────────────┐
 │ Authenticated?              │
 └──────────────┬──────────────┘
                │
                ├─ No → 401 Unauthorized
                │
                └─ Yes → 3. Atomic transaction with select_for_update():
                            - Lock existing like (if any)
                            - If like exists: DELETE → 204 No Content
                            - If not: CREATE → 201 Created
                            - Handle race conditions (IntegrityError)
                         4. Broadcast update via WebSocket
                         5. Return response
```

**Race Condition Handling:**
- Uses `select_for_update()` to lock row during check
- If concurrent requests try to create same like, second one deletes it (toggle behavior)

---

### 4.3 View Likes (Analytics API)

```
CLIENT
 │
 │ 1. GET /api/v1/likes/
 │    Query params: ?created__gte=2024-01-01&ordering=-likes
 ▼
 ┌─────────────────────────────┐
 │ LikeAPIView.list()          │
 │ Permission: None (public)   │
 └──────────────┬──────────────┘
                │
                │ 2. Aggregate likes by date
                ▼
 ┌─────────────────────────────┐
 │ Group by created__date      │
 │ Count likes per day         │
 │ Apply filters/ordering      │
 └──────────────┬──────────────┘
                │
                │ 3. Return 200 OK with aggregated data
```

**Response Example:**
```json
{
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

---

### 4.4 Batch Like Status (API)

```
CLIENT (Browser after back/forward navigation)
 │
 │ 1. GET /api/v1/likes/batch/?ids=1,2,3
 │    Authorization: Bearer <access_token>? (optional)
 ▼
 ┌─────────────────────────────┐
 │ LikeBatchAPIView.get()      │
 └──────────────┬──────────────┘
                │
                │ 2. Parse post IDs from query string
                │ 3. Get like counts for all posts
                │ 4. Get user's liked posts (if authenticated)
                ▼
 ┌─────────────────────────────┐
 │ Return 200 OK:              │
 │ {                           │
 │   "1": {count: 5, liked: true},│
 │   "2": {count: 3, liked: false}│
 │ }                           │
 └─────────────────────────────┘
```

**Use Case:**
- Used after browser back/forward navigation (bfcache restoration)
- WebSocket connection may be lost, so fetch fresh like data
- Updates UI with current counts and liked status

---

## 5. Real-time WebSocket Flow

### 5.1 WebSocket Connection & Like Updates

```
USER A (Viewing Post)          USER B (Viewing Same Post)
 │                              │
 │ 1. Page loads                │ 1. Page loads
 │ 2. fetch.js connects         │ 2. fetch.js connects
 ▼                              ▼
 ┌──────────────────────────┐  ┌──────────────────────────┐
 │ WebSocket:               │  │ WebSocket:               │
 │ ws://host/ws/socket-server/│  │ ws://host/ws/socket-server/│
 └──────────┬───────────────┘  └──────────┬───────────────┘
            │                              │
            │ 3. LikeConsumer.connect()    │ 3. LikeConsumer.connect()
            │ 4. Add to "likes" group      │ 4. Add to "likes" group
            │                              │
            │                              │
            │                              │
            │ 5. USER A clicks ❤          │
            ▼                              │
 ┌──────────────────────────┐              │
 │ Optimistic UI update     │              │
 │ (heart fills, count +1)  │              │
 └──────────┬───────────────┘              │
            │                              │
            │ 6. POST /api/v1/likes/toggle/│
            │    Authorization: Bearer ... │
            │                              │
            ▼                              │
 ┌──────────────────────────┐              │
 │ Server processes like    │              │
 │ - Create/Delete Like     │              │
 │ - Broadcast update       │              │
 └──────────┬───────────────┘              │
            │                              │
            ▼                              │
 ┌──────────────────────────┐              │
 │ Redis (Channel Layer)    │              │
 │ - Receives broadcast     │              │
 │ - Distributes to group   │              │
 └──────┬───────────┬───────┘              │
        │           │                      │
        │           └──────────────────────┘
        │                                 │
        ▼                                 ▼
 ┌──────────────────┐           ┌──────────────────┐
 │ LikeConsumer     │           │ LikeConsumer     │
 │ (User A)         │           │ (User B)         │
 └──────┬───────────┘           └──────┬───────────┘
        │                              │
        │ 7. Check user_id             │ 7. Check user_id
        │    Same as sender?           │    Different from sender?
        │    → Skip (already updated)  │    → Send message
        │                              │
        │                              ▼
        │                    ┌──────────────────┐
        │                    │ fetch.js receives│
        │                    │ {post_id, count} │
        │                    └──────┬───────────┘
        │                           │
        │                           │ 8. Update DOM
        │                           │    (count changes)
        │                           │
        │                           ▼
        │                    USER B sees new count! ✨
        │
        │ 9. Response 201/204
        ▼
 USER A already sees update
 (optimistic update)
```

**Key Points:**
- Optimistic updates: User who clicks sees immediate feedback
- Broadcast: All other users receive real-time updates
- Deduplication: Original user doesn't receive their own broadcast
- Persistence: Works across multiple server instances via Redis

---

## 6. Permission Matrix

### 6.1 Anonymous User

| Action | Endpoint | Result |
|--------|----------|--------|
| View published posts | `GET /` or `GET /posts/<pk>/` | ✅ Allowed |
| View unpublished posts | `GET /posts/<pk>/` | ❌ 403 Forbidden (unless owner) |
| Register | `POST /api/v1/users/` | ✅ Allowed |
| Create post | `POST /api/v1/posts/` | ❌ 401 Unauthorized |
| Like post | `POST /api/v1/likes/toggle/` | ❌ 401 Unauthorized |
| View analytics | `GET /api/v1/likes/` | ✅ Allowed |

---

### 6.2 Authenticated User (Regular)

| Action | Endpoint | Result |
|--------|----------|--------|
| View own profile | `GET /author/<own_pk>/` | ✅ Allowed |
| View other profile | `GET /author/<other_pk>/` | ❌ 403 Forbidden |
| Create post | `POST /api/v1/posts/` | ✅ Allowed (author = self) |
| Update own post | `PUT /api/v1/posts/<own_post>/` | ✅ Allowed |
| Update other post | `PUT /api/v1/posts/<other_post>/` | ❌ 403 Forbidden |
| Delete own post | `DELETE /api/v1/posts/<own_post>/` | ✅ Allowed |
| Like post | `POST /api/v1/likes/toggle/` | ✅ Allowed |
| View user list | `GET /api/v1/users/` | ❌ 403 Forbidden |
| Update own profile | `PATCH /api/v1/users/<own_pk>/` | ✅ Allowed |

---

### 6.3 Staff/Admin User

| Action | Endpoint | Result |
|--------|----------|--------|
| View any profile | `GET /author/<any_pk>/` | ✅ Allowed |
| View all posts | `GET /posts/` (staff view) | ✅ Allowed (including unpublished) |
| Update any post | `PUT /api/v1/posts/<any_post>/` | ✅ Allowed |
| Delete any post | `DELETE /api/v1/posts/<any_post>/` | ✅ Allowed |
| View user list | `GET /api/v1/users/` | ✅ Allowed |
| Update any user | `PATCH /api/v1/users/<any_pk>/` | ✅ Allowed |
| Delete any user | `DELETE /api/v1/users/<any_pk>/` | ✅ Allowed |

---

## 7. Token Refresh Flow

### 7.1 Access Token Expires

```
CLIENT
 │
 │ 1. GET /api/v1/posts/
 │    Authorization: Bearer <expired_access_token>
 ▼
 ┌─────────────────────────────┐
 │ JWTAuthentication           │
 │ Validates token             │
 └──────────────┬──────────────┘
                │
                │ 2. Token expired?
                ▼
 ┌─────────────────────────────┐
 │ Token Expired               │
 └──────────────┬──────────────┘
                │
                │ 3. Return 401 Unauthorized
                ▼
 CLIENT receives 401
 │
 │ 4. POST /api/v1/auth/token/refresh/
 │    Body: {refresh: "<refresh_token>"}
 │    OR Cookie: refresh_token=<refresh_token>
 ▼
 ┌─────────────────────────────┐
 │ MyTokenRefreshView          │
 │ (MyTokenRefreshSerializer)  │
 └──────────────┬──────────────┘
                │
                │ 5. Validate refresh token
                │ 6. Check blacklist
                ▼
 ┌─────────────────────────────┐
 │ Token Valid & Not Blacklisted?
 └──────────────┬──────────────┘
                │
                ├─ No → 401 Unauthorized
                │
                └─ Yes → 7. Generate NEW access token
                           8. Blacklist OLD refresh token (if rotation enabled)
                           9. Generate NEW refresh token (if rotation enabled)
                          10. Create OutstandingToken record
                          11. Return 200 OK:
                              {
                                "access": "eyJ0...",
                                "refresh": "eyJ1..." (if rotation)
                              }
                │
                │ 12. CLIENT retries original request with new access token
                ▼
 ┌─────────────────────────────┐
 │ GET /api/v1/posts/          │
 │ Authorization: Bearer <new> │
 └──────────────┬──────────────┘
                │
                │ 13. Request succeeds
                ▼
 ✅ Response 200 OK
```

**Token Rotation:**
- Old refresh token is blacklisted (cannot be reused)
- New refresh token issued for next refresh
- OutstandingToken table tracks all issued tokens for blacklist support

---

## 8. Image Processing Flow

### 8.1 Post with Image Upload

```
USER
 │
 │ 1. Creates/updates post with image
 │    POST /api/v1/posts/ with multipart/form-data
 ▼
 ┌─────────────────────────────┐
 │ Post.save()                 │
 │ Detects new/changed image   │
 └──────────────┬──────────────┘
                │
                │ 2. Save Post to database (image path stored)
                │ 3. Trigger Celery task (async)
                │    process_post_image.delay(post_id)
                │ 4. Return response immediately
                ▼
 ┌─────────────────────────────┐
 │ Response 201 Created        │
 │ (image URL may be raw)      │
 └─────────────────────────────┘

 (Meanwhile, asynchronously...)
                │
                ▼
 ┌─────────────────────────────┐
 │ Celery Worker               │
 │ process_post_image()        │
 └──────────────┬──────────────┘
                │
                │ 5. Load post from database
                │ 6. Read original image
                │ 7. Fix EXIF orientation
                │ 8. Resize to max 2000x2000
                │ 9. Generate thumbnail (300x300)
                │ 10. Save processed images
                │ 11. Update Post.image and Post.thumbnail
                ▼
 ┌─────────────────────────────┐
 │ Post updated                │
 │ (image + thumbnail ready)   │
 └─────────────────────────────┘
```

**Benefits:**
- Fast response (doesn't wait for image processing)
- Images processed asynchronously
- Thumbnails generated automatically
- EXIF orientation corrected (iPhone images display correctly)

---

## 9. Error Scenarios

### 9.1 Authentication Failures

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Invalid credentials (login) | 401 Unauthorized | `{"detail": "No active account found..."}` |
| Expired access token | 401 Unauthorized | `{"detail": "Token is invalid or expired"}` |
| Invalid refresh token | 401 Unauthorized | `{"detail": "Token is invalid or expired"}` |
| Blacklisted refresh token | 401 Unauthorized | `{"detail": "Token is blacklisted"}` |
| Missing Authorization header | 401 Unauthorized | `{"detail": "Authentication credentials were not provided"}` |

---

### 9.2 Permission Failures

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Anonymous accessing protected endpoint | 401 Unauthorized | `{"detail": "Authentication credentials..."}` |
| Regular user accessing staff-only | 403 Forbidden | `{"detail": "You do not have permission..."}` |
| User updating other's post | 403 Forbidden | `{"detail": "You do not have permission..."}` |
| User viewing unpublished post (not owner) | 403 Forbidden | `{"Forbidden": "Unpublished post can be retrieved by owner only!"}` |

---

### 9.3 Validation Failures

| Scenario | HTTP Status | Response |
|----------|-------------|----------|
| Invalid email format | 400 Bad Request | `{"email": ["Enter a valid email address."]}` |
| Passwords don't match | 400 Bad Request | `{"password2": ["Password fields didn't match."]}` |
| Profanity in content | 400 Bad Request | `{"content": ["Profanity detected"]}` |
| Missing required field | 400 Bad Request | `{"title": ["This field is required."]}` |
| Duplicate like | 400 Bad Request | Handled gracefully (toggles to unlike) |

---

## 10. Complete User Journey Examples

### 10.1 New User Registration to First Post

```
1. Anonymous user visits site
   → GET / → See published posts

2. User decides to register
   → GET /signup/ → Show registration form
   → POST /signup/ → Create account, auto-login, redirect to profile

3. User sees own profile
   → GET /author/<pk>/ → Profile page with empty posts list

4. User wants to create first post
   → GET /posts/add/ → Show post creation form
   → POST /posts/add/ → Create post, redirect to homepage
   → Celery processes image in background

5. User sees post on homepage
   → GET / → Homepage shows new post (with like count)
   → WebSocket connected for real-time updates

6. User clicks heart on their own post
   → POST /api/v1/likes/toggle/ → Like created
   → WebSocket broadcasts → All users see updated count
```

---

### 10.2 API Client Journey

```
1. Client registers user
   → POST /api/v1/users/ → 201 Created, returns user data

2. Client logs in
   → POST /api/v1/auth/login/ → 200 OK, returns {access, refresh}

3. Client accesses protected endpoint
   → GET /api/v1/posts/ Authorization: Bearer <access> → 200 OK

4. Access token expires (after 5 min)
   → GET /api/v1/posts/ Authorization: Bearer <expired> → 401 Unauthorized

5. Client refreshes token
   → POST /api/v1/auth/token/refresh/ {refresh: "..."} → 200 OK, new tokens

6. Client retries with new token
   → GET /api/v1/posts/ Authorization: Bearer <new> → 200 OK

7. Client creates post
   → POST /api/v1/posts/ Authorization: Bearer <new> → 201 Created

8. Client likes post
   → POST /api/v1/likes/toggle/ Authorization: Bearer <new> → 201 Created
```

---

This document covers all major user paths and scenarios in the Postways application. Each flow includes authentication checks, permission validations, and error handling.
