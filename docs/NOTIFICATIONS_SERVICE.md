# Notification Service (Kafka Microservice)

A standalone FastAPI microservice that sends email notifications when a user likes a post. It communicates with the Django app via Apache Kafka, demonstrating microservice architecture patterns.

## Architecture Overview

```
┌──────────────┐         ┌─────────────┐         ┌──────────────────────┐
│    Django     │         │    Kafka    │         │ Notification Service │
│  (producer)   │────────>│   (broker)  │────────>│  (FastAPI consumer)  │
│               │  event  │             │ consume │                      │
│ Like created  │         │ topic:      │         │ - Reads event        │
│ in API view   │         │ post-events │         │ - Filters self-likes │
└──────────────┘         └─────────────┘         │ - Sends email        │
                                                  └──────────────────────┘
```

### Why a Separate Service?

| Aspect | Django app (monolith) | Notification service (microservice) |
|---|---|---|
| **Runtime** | Runs inside the Django process | Runs in its own container |
| **Dependencies** | Shares Django's `pyproject.toml` | Has its own `pyproject.toml` |
| **Framework** | Django | FastAPI |
| **Communication** | Direct Python imports | Via Kafka (network boundary) |
| **Database** | PostgreSQL | None (stateless) |
| **Deployment** | Deployed with Django | Can be deployed independently |

The network boundary (Kafka) is what makes this a microservice. Django doesn't know or care who consumes the events.

## How It Works (Step by Step)

### Step 1: User Likes a Post

A user clicks the heart button or sends `POST /api/v1/likes/` with `{"post": <id>}`.

### Step 2: Django Produces a Kafka Event

In `apps/diary/views/api.py`, `LikeCreateDestroyAPIView.create()`:

1. The like is saved in a database transaction
2. After the transaction commits (`transaction.on_commit`), two things happen:
   - The existing WebSocket broadcast for real-time UI updates
   - **New**: `publish_post_liked_event()` publishes an event to Kafka

The event is only published when a **new like is created** (not on unlike or self-like toggle).

The producer is **fire-and-forget**: if Kafka is down, the error is logged but the like endpoint still returns successfully.

### Step 3: Kafka Stores the Event

The event is written to the `post-events` topic, partitioned by `post_id` (so all events for the same post are ordered). The topic is auto-created on the first message.

### Step 4: Notification Service Consumes the Event

The FastAPI app runs a Kafka consumer in a background thread. When it receives a `post.liked` event:

1. Parses the JSON payload
2. Checks if `liker_id == author_id` (skips self-likes)
3. Sends an email notification to the post author

### Step 5: Email is Sent

In development, the email is logged to the container's stdout (visible via `docker logs`). In production, this would use SMTP.

## Kafka Event Schema

Topic: `post-events`

```json
{
  "event_type": "post.liked",
  "timestamp": "2026-04-03T15:26:41.123456+00:00",
  "data": {
    "like_id": 42,
    "post_id": 7,
    "post_title": "My First Blog Post",
    "liker_id": 3,
    "liker_username": "john_doe",
    "author_id": 1,
    "author_email": "jane@example.com",
    "author_username": "jane_smith"
  }
}
```

The event carries all data the consumer needs. The notification service never calls back to Django or accesses the database.

The `event_type` field allows the topic to carry other event types in the future (e.g., `post.created`, `user.registered`).

## Key Files

### Django Side (Producer)

| File | Purpose |
|------|---------|
| `apps/diary/kafka_producer.py` | Singleton Kafka producer with `publish_post_liked_event()` |
| `apps/diary/views/api.py` | `LikeCreateDestroyAPIView.create()` — publishes event on new like |
| `config/settings.py` | `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC_POST_EVENTS` settings |

### Notification Service (Consumer)

| File | Purpose |
|------|---------|
| `services/notifications/Dockerfile` | Container image (Python 3.12 + uv) |
| `services/notifications/pyproject.toml` | Dependencies (FastAPI, confluent-kafka, pydantic-settings) |
| `services/notifications/app/main.py` | FastAPI app, manages consumer lifecycle in background thread |
| `services/notifications/app/consumer.py` | Kafka consumer loop, message processing, self-like filtering |
| `services/notifications/app/email.py` | Email sending (logs to console in dev) |
| `services/notifications/app/config.py` | Settings from environment variables |

### Infrastructure

| File | Purpose |
|------|---------|
| `docker/docker-compose.dev.yml` | Kafka broker (KRaft mode) and notification service containers |

## Docker Services

### Kafka Broker

- Image: `apache/kafka:3.9.0`
- Mode: KRaft (no Zookeeper required)
- Internal port: `9092` (broker), `9093` (controller)
- Auto-creates topics on first produce
- Single partition/replica (dev setup)

### Notification Service

- Built from: `services/notifications/Dockerfile`
- Port: `8001` (health endpoint)
- Depends on: Kafka (healthy)
- Health check: `GET http://localhost:8001/health`

## Configuration

### Django Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker address |
| `KAFKA_TOPIC_POST_EVENTS` | `post-events` | Topic name for post events |

### Notification Service Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `NOTIFICATIONS_KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker address |
| `NOTIFICATIONS_KAFKA_TOPIC` | `post-events` | Topic to subscribe to |
| `NOTIFICATIONS_KAFKA_CONSUMER_GROUP` | `notifications-service` | Consumer group ID |

## Running and Testing

### Start All Services

```bash
docker compose -f docker/docker-compose.dev.yml up --build
```

### Watch Notification Logs

```bash
docker logs postways-v2-notifications-1 -f
```

### Check Health

```bash
curl http://localhost:8001/health
```

Response:
```json
{"status": "ok", "consumer_alive": true}
```

### Test Scenarios

| Action | Expected Result |
|---|---|
| Like another user's post | Email notification logged in notification service |
| Like your own post | No notification (self-like filtered) |
| Unlike a post (toggle off) | No notification (only new likes trigger events) |
| Kafka is down when liking | Like succeeds, error logged in Django, no notification |

## Key Design Decisions

### Fire-and-Forget Producer

The Kafka producer in Django catches all exceptions and logs them. A Kafka outage never prevents a user from liking a post. This is the right trade-off because notifications are not critical — a missed "someone liked your post" email is far less harmful than a broken like button.

### Data in the Event

The event contains all data needed by the consumer (author email, usernames, post title). This means:
- The notification service doesn't need database access
- The notification service doesn't need to call Django's API
- Services are truly decoupled

The trade-off is that the event is larger, and data could be stale if (e.g.) the author changes their email between the like and the notification. For this use case, that's acceptable.

### Consumer Group

The notification service uses a Kafka consumer group (`notifications-service`). This means:
- Kafka tracks which messages have been consumed (offset management)
- If the service restarts, it picks up where it left off
- If you scale to multiple instances, Kafka distributes partitions across them

### Topic Auto-Creation

Topics are auto-created when the producer first writes. The `UNKNOWN_TOPIC_OR_PART` errors in the consumer logs on first startup are normal — they stop once Django publishes the first event.

## Future Enhancements

These are not implemented but would be natural next steps:

- **SMTP integration** in the notification service for real email delivery
- **Additional event types** on the same topic (`post.created`, `user.registered`)
- **Second consumer** (e.g., analytics service) reading the same `post-events` topic
- **Dead letter queue** for failed notification processing
- **Notification preferences** database (opt-out of like notifications)
- **Rate limiting** (batch multiple likes into a single digest email)
