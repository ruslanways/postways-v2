# API Documentation Guide

This guide describes how to document API endpoints that support multiple HTTP methods and different permissions, so the docs stay clear and maintainable.

## Principles

1. **Single source of truth** — Document each (path, method) pair in one place. Avoid duplicating permission rules in multiple docs.
2. **Method × permission is first-class** — For every path, make it obvious which method requires which access (anonymous, authenticated, owner, staff, admin).
3. **Consistent permission labels** — Use the same terms everywhere: Anonymous, Authenticated, Owner, Staff, Admin, OwnerOrAdmin.
4. **Scannable quick reference** — Provide a compact table (path + method + permission) for quick lookup; detailed request/response can follow.

## Recommended structure per resource

For each **path** (e.g. `/api/v1/posts/`, `/api/v1/posts/<id>/`):

1. **Method matrix (required)**  
   One table at the top of the section:

   | Method | Permission    | Request body        | Response            |
   | ------ | ------------- | ------------------- | ------------------- |
   | GET    | Anonymous     | —                   | 200, paginated list |
   | POST   | Authenticated | multipart/form-data | 201 Created         |

   This is the canonical answer to “who can call what on this path?”

2. **Detailed sections (optional)**  
   Under the table, keep detailed request/response examples, query params, and notes only where they add value (e.g. non-obvious behavior, security notes).

3. **Cross-references**  
   Link from the matrix to detailed sections (e.g. “See [POST details](#post-apiv1posts) for request body and validation.”).

## Example: Posts resource

```markdown
### `/api/v1/posts/`

| Method | Permission    | Request                                                                       | Response                             |
| ------ | ------------- | ----------------------------------------------------------------------------- | ------------------------------------ |
| GET    | Anonymous     | Query: `author`, `created_at__gte`, `ordering`, `page`, `page_size`, `search` | 200, paginated list (published only) |
| POST   | Authenticated | multipart/form-data: `title`, `content`, `image?`, `published?`               | 201 Created                          |

- **GET**: Published posts only. Authenticated users get `has_liked` in `stats`.
- **POST**: Author set to current user. Profanity check; image processed async (Celery).

### `/api/v1/posts/<id>/`

| Method      | Permission     | Request                                                       | Response                                                |
| ----------- | -------------- | ------------------------------------------------------------- | ------------------------------------------------------- |
| GET         | Anonymous\*    | —                                                             | 200 single post; 403 if unpublished and not owner/admin |
| PUT / PATCH | Owner only     | (PATCH: partial) `title?`, `content?`, `image?`, `published?` | 200 OK                                                  |
| DELETE      | Owner or Admin | —                                                             | 204 No Content                                          |

\* Unpublished: owner or admin only.
```

This keeps “method + permission” in one place per path and avoids repeating it in long prose.

## Where to maintain the docs

- **Current approach (markdown only)**  
  Keep `docs/endpoints-reference.md` as the single source. Add a **method matrix table at the start of each path section** (as above). Keep the existing “Authentication Summary” tables at the end as the global quick reference; regenerate or update them when you add/change endpoints so they stay in sync with the per-resource matrices.

- **Optional: OpenAPI as source of truth**  
  Use [drf-spectacular](https://drf-spectacular.readthedocs.io/) (or similar) to generate an OpenAPI 3 schema from your DRF views. Then:
  - **Permissions**: Document per-view in code (e.g. `permission_classes`, custom permissions); drf-spectacular can expose them in the schema (`security` / operation description).
  - **Single source**: The schema is the canonical list of paths, methods, and (if you document them) permissions; human-readable docs can be generated from it or written to match it.
  - **Tooling**: Swagger UI/ReDoc for interactive docs; client generation; and consistent structure across endpoints.

If you introduce OpenAPI, keep the same **method × permission** idea: for each path + method in the schema, ensure “who can call this” is explicit (in description or security).

## Permission label reference

Use these consistently in matrices and summary tables:

| Label         | Meaning                                             |
| ------------- | --------------------------------------------------- |
| Anonymous     | No auth required                                    |
| Authenticated | Valid JWT (or session for HTML)                     |
| Owner         | Resource belongs to current user                    |
| Staff         | `user.is_staff`                                     |
| Admin         | Same as Staff in this project                       |
| OwnerOrAdmin  | Owner or staff                                      |
| Owner only    | Only the resource owner (e.g. update post)          |
| Owner/Admin   | Owner or staff (e.g. delete post, view unpublished) |

Add short notes in the matrix when it matters (e.g. “POST = Anonymous (registration only)” for `/api/v1/users/`).

## Checklist when adding or changing an endpoint

- [ ] Add or update the **row** for (path, method) in that path’s method matrix.
- [ ] Update the **Authentication Summary** table at the end of `endpoints-reference.md` so the global list stays correct.
- [ ] If you use OpenAPI, regenerate the schema and ensure the new/updated operation has the right permission description or security.
- [ ] Use the same permission labels as in this guide.

Following this structure keeps “many HTTP methods and different permissions” easy to read and maintain, whether you stay with markdown only or add OpenAPI later.
