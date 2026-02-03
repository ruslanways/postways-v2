# Production Deployment Guide - AWS Lightsail

This guide covers deploying Postways v2 to an AWS Lightsail instance with Docker and Nginx.

## Architecture Overview

```
                    ┌──────────────┐
                    │  CloudFlare  │
        Internet───>│  (SSL + CDN) │
                    └──────┬───────┘
                           │ HTTPS :443 (Origin cert)
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  AWS Lightsail Instance                         │
│                  /srv/postways-v2                               │
│                                                                 │
│  ┌─────────┐    ┌─────────────────────────────────────────┐    │
│  │ Nginx   │───>│ Docker Network (postways-v2-prod)       │    │
│  │ :443    │    │                                         │    │
│  └─────────┘    │  ┌─────────┐  ┌─────────┐  ┌─────────┐ │    │
│       │         │  │  Web    │  │ Celery  │  │ Celery  │ │    │
│       │         │  │ Daphne  │  │ Worker  │  │  Beat   │ │    │
│       ▼         │  │  :8000  │  │         │  │         │ │    │
│  /static/       │  └────┬────┘  └────┬────┘  └────┬────┘ │    │
│  (volume)       │       │            │            │      │    │
│                 │       ▼            ▼            ▼      │    │
│                 │  ┌─────────┐  ┌─────────────────────┐  │    │
│                 │  │Postgres │  │       Redis         │  │    │
│                 │  │  :5432  │  │       :6379         │  │    │
│                 │  └─────────┘  └─────────────────────┘  │    │
│                 └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                           │
                           │ Media uploads
                           ▼
                    ┌──────────────┐
                    │   AWS S3     │──── CloudFlare CDN (optional)
                    │   (media)    │
                    └──────────────┘
```

## Prerequisites

- AWS Lightsail instance (Ubuntu 22.04+ recommended)
- Docker and Docker Compose installed
- Domain pointed to your Lightsail IP
- AWS S3 bucket for media storage
- CloudFlare (optional, for SSL and CDN)

## Files Overview

| File                             | Purpose                              |
| -------------------------------- | ------------------------------------ |
| `docker/docker-compose.prod.yml` | Production compose with all services |
| `docker/nginx/nginx.conf`        | Nginx reverse proxy configuration    |
| `config/env.prod.example`        | Production environment template      |

## Step-by-Step Deployment

### 1. Prepare Lightsail Instance

```bash
# SSH into your Lightsail instance
ssh -i your-key.pem ubuntu@your-lightsail-ip
```

### 2. Clone Repository

```bash
cd /srv/postways-v2

# Clone your repository
git clone https://github.com/your-username/postways-v2.git .

# Or copy files via rsync from local machine:
# rsync -avz --exclude '.git' --exclude '.venv' . user@lightsail:/srv/postways-v2/
```

### 3. Configure Environment

```bash
cd /srv/postways-v2

# Copy production environment template
cp config/env.prod.example config/.env

# Edit with your production values
nano config/.env
```

**Critical values to set:**

- `DJANGO_SECRET_KEY` - Generate a new one
- `ALLOWED_HOSTS` - Your domain(s)
- `CSRF_TRUSTED_ORIGINS` - Your domain(s) with https://
- `DATABASE_URL` and `POSTGRES_*` - Use strong password
- `AWS_*` - Your S3 credentials
- `EMAIL_*` - Your SMTP settings

### 4. Build and Deploy

```bash
cd /srv/postways-v2

# Build images
docker compose -f docker/docker-compose.prod.yml build

# Start services
docker compose -f docker/docker-compose.prod.yml up -d

# Apply migrations
docker compose -f docker/docker-compose.prod.yml exec web python manage.py migrate --noinput

# Collect static files
docker compose -f docker/docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# Check logs
docker compose -f docker/docker-compose.prod.yml logs -f

# Verify all services are healthy
docker compose -f docker/docker-compose.prod.yml ps
```

### 5. Initial Setup

```bash
# Create superuser (if needed)
docker compose -f docker/docker-compose.prod.yml exec web python manage.py createsuperuser

# Seed demo data (optional)
docker compose -f docker/docker-compose.prod.yml exec web python manage.py seed_demo_data
```

### 6. Setup SSL Certificates

The server uses CloudFlare Origin certificates for end-to-end encryption.

**On your Lightsail server:**

```bash
# Create directory for certificates
sudo mkdir -p /etc/ssl/cloudflare

# Copy your CloudFlare Origin certificate and key
# (download from CloudFlare Dashboard → SSL/TLS → Origin Server)
sudo nano /etc/ssl/cloudflare/origin.crt  # Paste certificate
sudo nano /etc/ssl/cloudflare/origin.key  # Paste private key

# Set proper permissions
sudo chmod 600 /etc/ssl/cloudflare/origin.key
sudo chmod 644 /etc/ssl/cloudflare/origin.crt
```

### 7. Configure CloudFlare

**SSL/TLS Settings:**

1. SSL/TLS mode: **"Full"** - CloudFlare connects to origin via HTTPS
2. Enable "Always Use HTTPS"
3. Edge Certificates: Universal SSL (or your own)

**Caching Rules:**

- Cache static assets (`/static/*`) - Page Rule: Cache Level = Cache Everything
- Bypass cache for API (`/api/*`) - Page Rule: Cache Level = Bypass
- Bypass cache for WebSocket (`/ws/*`) - Already bypassed by default

**WebSocket:**

- Ensure WebSockets are enabled (Network → WebSockets)

**Media CDN (optional):**

- Set `CDN_DOMAIN` in `.env` to your CloudFlare-proxied subdomain for S3
- Or use CloudFlare R2 instead of S3 for tighter integration

### 8. Firewall Configuration

```bash
# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
```

## Static Files

Static files are collected manually after each deploy:

1. **After deploy**: Run `collectstatic` manually (see commands below)
2. **Volume mount**: Static files are stored in `static_files` volume
3. **Nginx serves**: Directly from `/var/www/postways-v2/static/`

```bash
docker compose -f docker/docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

The `ManifestStaticFilesStorage` backend hashes filenames for cache busting.

## Updating the Application

```bash
cd /srv/postways-v2

# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker/docker-compose.prod.yml build
docker compose -f docker/docker-compose.prod.yml up -d

# Re-resolve web container IP (nginx caches DNS)
docker compose -f docker/docker-compose.prod.yml restart nginx

# Apply migrations (if any)
docker compose -f docker/docker-compose.prod.yml exec web python manage.py migrate --noinput

# Collect static files (if changed)
docker compose -f docker/docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

### Zero-Downtime Deployment (Optional)

For zero-downtime updates, you can use rolling updates:

```bash
# Scale web service
docker compose -f docker/docker-compose.prod.yml up -d --scale web=2 --no-recreate

# Wait for new container to be healthy
sleep 30

# Remove old container
docker compose -f docker/docker-compose.prod.yml up -d --scale web=1
```

## Monitoring & Maintenance

### View Logs

```bash
# All services
docker compose -f docker/docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker/docker-compose.prod.yml logs -f web
docker compose -f docker/docker-compose.prod.yml logs -f celery_worker
docker compose -f docker/docker-compose.prod.yml logs -f nginx
```

### Health Checks

**Docker healthchecks (automatic):**
- **web**: TCP port check on 8000 (verifies Daphne is accepting connections, bypasses Django ALLOWED_HOSTS)
- **nginx**: HTTP check on `/health` (nginx's own endpoint, returns "healthy" directly)
- **db**: `pg_isready` command
- **redis**: `redis-cli ping`

**Manual checks:**

```bash
# Check service status
docker compose -f docker/docker-compose.prod.yml ps

# Check nginx health (nginx's own /health endpoint on port 80)
curl http://localhost/health

# Check Django is responding (via API root)
docker compose -f docker/docker-compose.prod.yml exec web python -c "import socket; s=socket.socket(); s.connect(('localhost', 8000)); s.close(); print('OK')"
```

### Database Backup

```bash
# Create backup
docker compose -f docker/docker-compose.prod.yml exec db \
  pg_dump -U postways_user postways_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
cat backup.sql | docker compose -f docker/docker-compose.prod.yml exec -T db \
  psql -U postways_user postways_db
```

### Cleanup

```bash
# Remove unused images
docker image prune -f

# Remove unused volumes (careful!)
docker volume prune -f

# Full cleanup (removes stopped containers, networks, images)
docker system prune -f
```

## Troubleshooting

### WebSocket Not Connecting

1. Check CloudFlare WebSocket setting is enabled
2. Verify nginx WebSocket config (proxy_upgrade headers)
3. Check Django ALLOWED_HOSTS includes your domain

### Static Files Not Loading

```bash
# Manually run collectstatic
docker compose -f docker/docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# Check volume contents
docker compose -f docker/docker-compose.prod.yml exec nginx ls -la /var/www/postways-v2/static/
```

### Database Connection Issues

```bash
# Check if db container is running
docker compose -f docker/docker-compose.prod.yml ps db

# Check db logs
docker compose -f docker/docker-compose.prod.yml logs db

# Test connection from web container
docker compose -f docker/docker-compose.prod.yml exec web python manage.py dbshell
```

### Memory Issues

Lightsail instances can be resource-constrained. Monitor with:

```bash
# Check container resource usage
docker stats

# Reduce Celery concurrency in docker-compose.prod.yml if needed
# Change: --concurrency=2 to --concurrency=1
```

## Security Checklist

- [ ] Strong `DJANGO_SECRET_KEY` generated
- [ ] Strong database password set
- [ ] S3 bucket has proper IAM permissions (not public write)
- [ ] Firewall enabled (only 80/443 open)
- [ ] CloudFlare proxy enabled (hides origin IP)
- [ ] `DEBUG=False` confirmed (via `DJANGO_ENV=production`)
- [ ] No `.env` file committed to git
- [ ] Admin path accessible only via VPN/IP whitelist (optional)
