# Postways – Production Runbook

> **Lightsail · Docker Compose · Cloudflare**

This is the **single source of truth** for production operations.  
Follow it literally. When unsure → use the [Safe Default Deploy](#3-safe-default-deploy).

---

## Quick Reference

| Task | Section |
|------|---------|
| Deploy with changes | [§3 Safe Default Deploy](#3-safe-default-deploy) |
| Deploy code-only | [§4 Fast Deploy](#4-fast-deploy) |
| After server reboot | [§5 Restart](#5-restart-after-reboot) |
| Check logs | [§9 Logs](#9-logs) |
| Rollback | [§10 Rollback](#10-rollback) |

---

## 0. Environment Overview

### Server

| Item | Value |
|------|-------|
| User | `ubuntu` |
| Project dir | `/srv/postways-v2` |
| Compose file | `docker/docker-compose.prod.yml` |

### Services

| Service | Description |
|---------|-------------|
| `web` | Django + Daphne (ASGI) |
| `nginx` | Reverse proxy (80/443) |
| `db` | PostgreSQL |
| `redis` | Redis |
| `celery_worker` | Background tasks |
| `celery_beat` | Scheduled tasks |

### Static Files

```
Django writes → /app/staticfiles (inside web container)
Nginx serves  → /var/www/postways-v2/static
Shared via    → static_files volume
Django config → STATIC_ROOT = BASE_DIR / "staticfiles"
```

### TLS

- Cloudflare SSL mode: **Full**
- Origin certs:
  - `/etc/ssl/cloudflare/origin.crt`
  - `/etc/ssl/cloudflare/origin.key`

---

## 1. Connect & Prepare

```bash
ssh ubuntu@<server-ip>
cd /srv/postways-v2
```

Set up the session alias:

```bash
alias dc='docker compose -f docker/docker-compose.prod.yml'
```

---

## 2. Check Status First

**Always run this before any operation:**

```bash
dc ps
```

If something looks wrong:

```bash
dc logs -n 100 web
dc logs -n 100 nginx
```

---

## 3. Safe Default Deploy

> ✅ **Use this when unsure** — it handles everything safely.

**When to use:**
- New features
- Model/migration changes
- Static file changes
- Dependency changes
- Environment variable changes

```bash
git pull
dc up -d --build db redis
dc run --rm web python manage.py migrate --noinput
dc run --rm web python manage.py collectstatic --noinput
dc up -d --build
dc restart nginx  # re-resolve web container IP
```

**Notes:**
- Safe to run while containers are already running
- Expect brief WebSocket reconnects when `web` is recreated
- Migrations are serialized by Django/DB locks

---

## 4. Fast Deploy

> ⚡ Code-only changes — no migrations, no static updates.

**Only use when ALL of these are true:**
- No new migrations
- No static file changes
- No env changes

```bash
git pull
dc up -d --build
dc restart nginx  # re-resolve web container IP
```

---

## 5. Restart After Reboot

> 🔄 After `sudo reboot` or Docker daemon restart.

```bash
dc up -d
```

**⚠️ Do NOT run migrate or collectstatic here.**

---

## 6. Verify Static Volume

Check that Django and Nginx see the same files:

```bash
dc exec web ls -la /app/staticfiles | head
dc exec nginx ls -la /var/www/postways-v2/static | head
```

If outputs differ → static volume wiring is broken.

---

## 7. Nginx Config Changes

Config mount: `./nginx/nginx.conf → /etc/nginx/nginx.conf` (read-only)

Validate and reload:

```bash
dc exec nginx nginx -t
dc exec nginx nginx -s reload
```

---

## 8. Connectivity Checks

**From inside Docker network:**

```bash
# Verify web container is accepting connections
dc exec web python -c "import socket; s=socket.socket(); s.connect(('localhost', 8000)); s.close(); print('OK')"
```

**From your laptop — verify:**
- [ ] https://postways.net loads
- [ ] Login works
- [ ] Image upload works (S3)
- [ ] Likes update live (WebSockets `/ws/socket-server/`)

---

## 9. Logs

```bash
dc logs -f web            # Django/Daphne
dc logs -f nginx          # Reverse proxy
dc logs -f celery_worker  # Background tasks
dc logs -f celery_beat    # Scheduled tasks
```

Add `-n 100` to limit output: `dc logs -n 100 web`

---

## 10. Rollback

> ⚠️ Code only — migrations are NOT automatically rolled back.

```bash
git log --oneline -10
git checkout <commit_or_tag>
dc up -d --build
```

If schema already changed → fix forward.

---

## 11. Maintenance

**OS updates (monthly/quarterly):**

```bash
sudo apt update
sudo apt -y upgrade
sudo reboot
```

After reboot:

```bash
dc up -d
```

---

## 12. Do NOT Do These Things

| ❌ Don't | Why |
|----------|-----|
| Run migrate/collectstatic on container startup | Use explicit deploy commands |
| Commit `.env` or TLS private keys | Security risk |
| Expose DB or Redis ports | Security risk |
| Use Cloudflare "Flexible" SSL | Insecure origin connection |
| Edit code in running containers | Changes lost on restart |

---

## 13. Mental Model

```
Compose         = steady state (what should be running)
Deploy commands = intentional one-time actions
Restart         ≠ deploy
Boring prod     = good prod
```

**When in doubt → use [Safe Default Deploy](#3-safe-default-deploy).**
