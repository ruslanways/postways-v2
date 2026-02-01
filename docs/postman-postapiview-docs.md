## `GET /api/v1/posts/`

List published posts.

**Description**  
Returns a paginated list of published posts with like counts and stats. Supports filtering by author and date, ordering by `id`, `updated_at`, or `created_at`, and search in title and content. Default ordering is by `updated_at` descending (most recently updated first), with `id` as tie-breaker for stable pagination. If the posts list is accessed with an authenticated user, each item’s `stats` object will include `has_liked` (whether the current user has liked that post); for anonymous requests, `has_liked` is omitted.

**Access**

- No authentication required (read-only).

**Query parameters**

- `page` (optional, integer) – Page number of the results to fetch.
- `page_size` (optional, integer) – Number of results per page (default: 10).
- `author` (optional, integer) – Filter by author user ID (exact).
- `author__username` (optional, string) – Filter by username (exact or contains).
- `created_at__gte` (optional, ISO date) – Posts created on or after this date.
- `created_at__lte` (optional, ISO date) – Posts created on or before this date.
- `created_at__date__range` (optional, date,date) – Posts created within date range (e.g. `2024-01-01,2024-12-31`).
- `updated_at__gte` (optional, ISO date) – Posts updated on or after this date.
- `updated_at__lte` (optional, ISO date) – Posts updated on or before this date.
- `ordering` (optional, string) – Order by: `id`, `updated_at`, or `created_at`; prefix with `-` for descending (e.g. `-updated_at`).
- `search` (optional, string) – Search in title and content.

**Response**  
Returns a JSON object containing a paginated list of posts. When the request is authenticated, each item’s `stats` includes `has_liked`; for anonymous requests, `has_liked` is omitted.

```json
{
    "count": 42,
    "next": "http://localhost:8000/api/v1/posts/?page=2&page_size=10",
    "previous": null,
    "results": [
        {
            "url": "http://localhost:8000/api/v1/posts/3/",
            "id": 3,
            "author": {
                "id": 2,
                "username": "jane",
                "url": "http://localhost:8000/api/v1/users/2/"
            },
            "title": "My First Post",
            "content_excerpt": "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud...",
            "thumbnail": "http://localhost:8000/media/diary/images/thumbnails/post_3_thumb.jpg",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T14:30:00Z",
            "stats": {
                "like_count": 5,
                "has_liked": false
            }
        },
        {
            "url": "http://localhost:8000/api/v1/posts/2/",
            "id": 2,
            "author": {
                "id": 1,
                "username": "alice",
                "url": "http://localhost:8000/api/v1/users/1/"
            },
            "title": "Short post",
            "content_excerpt": "Just a short message.",
            "thumbnail": null,
            "created_at": "2024-01-14T09:00:00Z",
            "updated_at": "2024-01-14T09:00:00Z",
            "stats": {
                "like_count": 0,
                "has_liked": true
            }
        }
    ]
}
```

Typical successful status code: `200 OK`.

---

## `POST /api/v1/posts/`

Create a new post.

**Description**  
Creates a new post. The author is set automatically to the authenticated user. Content is validated for profanity. If an image is provided, it is processed asynchronously (resize, thumbnail, EXIF orientation) via Celery.

**Access**

- Authenticated users only (JWT in `Authorization: Bearer <access_token>`).

**Request body**  
Send as `multipart/form-data`. Example fields:

- `title` (required, string) – Post title
- `content` (required, string) – Post body
- `image` (optional, file) – Image file; processed asynchronously
- `published` (optional, boolean) – Whether the post is published (default: `true`; set `false` for draft)

**Behavior**

- Validates the input (e.g. title and content required; content checked for profanity).
- Sets the post author to the current user.
- On success, creates the post and returns the created resource.
- If an image is uploaded, queues background processing (resize, thumbnail, EXIF fix).

**Response**  
On success, returns the created post resource.

```json
{
    "url": "http://localhost:8000/api/v1/posts/7/",
    "id": 7,
    "author": "http://localhost:8000/api/v1/users/1/",
    "title": "My new post",
    "content": "Post content goes here. Can be longer than the list excerpt.",
    "image": "http://localhost:8000/media/diary/images/post_7.jpg",
    "created_at": "2024-01-16T12:00:00Z",
    "updated_at": "2024-01-16T12:00:00Z",
    "published": true
}
```

Typical successful status code: `201 Created`.
