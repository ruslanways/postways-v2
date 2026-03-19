# Add Kafka Example to Postways

## Context

You want to learn Kafka by adding a simple, real integration to the project. The goal: when actions happen in the app (login, create post, like), events are published to a Kafka topic. You run a consumer in a second terminal and watch events stream in real-time.

This is a **learning exercise** — Kafka is non-critical and the app works fine without it.

## What You'll Learn

- Kafka broker setup (KRaft mode, no Zookeeper)
- Producers (publishing JSON messages to a topic)
- Consumers (subscribing to a topic and reading messages)
- Topics, partitions, consumer groups, offsets

## Plan (6 changes, 2 new files)

### 1. Add Kafka to Docker Compose
**File:** `docker/docker-compose.dev.yml`
- Add `kafka` service using `bitnami/kafka:4.2` in KRaft mode (modern — no Zookeeper)
- Add `postways-v2-kafka_data` volume
- Web does NOT depend on Kafka (graceful degradation — app works without it)

### 2. Add `confluent-kafka` dependency
**File:** `pyproject.toml`
- Add `"confluent-kafka>=2.8,<3.0"` to dependencies
- Ships prebuilt wheels, no C compiler needed

### 3. Add Kafka setting
**File:** `config/settings.py` (after Celery section, line ~352)
- Add `KAFKA_BOOTSTRAP_SERVERS = env("KAFKA_BOOTSTRAP_SERVERS", default="kafka:9092")`

### 4. Create producer module (NEW)
**File:** `apps/diary/kafka_producer.py`
- `publish_event(topic, event_type, data)` function
- Lazy singleton `Producer` instance (created on first call)
- JSON serialization with consistent schema: `{event_type, timestamp, data}`
- Graceful failure — logs warning if Kafka unavailable, never breaks the app

### 5. Hook into Django signals
**File:** `apps/diary/signals.py`
- Extend existing `log_user_login` → also publish `user.logged_in` event
- Add `post_save` receiver for `Post` → publish `post.created` / `post.updated`
- Add `post_save` receiver for `Like` → publish `like.created`
- Uses lazy imports (matches existing pattern in `queue_post_image_deletion`)

### 6. Create consumer management command (NEW)
**File:** `apps/diary/management/commands/kafka_consumer.py`
- Django management command that subscribes to `diary-events` topic
- Polls for messages, pretty-prints them to stdout
- `auto.offset.reset: earliest` — sees all historical events
- Clean shutdown on Ctrl+C

## How to Try It

```bash
# 1. Rebuild
uv lock
docker compose -f docker/docker-compose.dev.yml build web

# 2. Start everything (including Kafka)
docker compose -f docker/docker-compose.dev.yml up -d

# 3. Wait ~30s for Kafka to initialize, then in a second terminal:
docker compose -f docker/docker-compose.dev.yml exec web python manage.py kafka_consumer

# 4. In the browser: log in, create a post, like something
# 5. Watch events appear in the consumer terminal!
```

Expected output:
```
[2026-02-24T14:30:01+00:00] user.logged_in
  user_id: 1
  username: admin

[2026-02-24T14:30:15+00:00] post.created
  post_id: 42
  title: My First Post
  author_id: 1
  author_username: admin
  published: True

[2026-02-24T14:30:22+00:00] like.created
  like_id: 7
  user_id: 2
  post_id: 42
```
