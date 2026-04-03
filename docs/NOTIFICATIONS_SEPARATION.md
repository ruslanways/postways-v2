# Separating the Notification Service into Its Own Repository

The notification service (`services/notifications/`) is already fully self-contained — it has its own Dockerfile, dependencies, and no shared code with Django. These steps move it to a separate repository for a true microservice setup.

## Step 1: Create a New Repository

```bash
# Create new repo on GitHub
gh repo create postways-notifications --private --clone

# Copy the service files
cp -r services/notifications/* postways-notifications/
cd postways-notifications
git add .
git commit -m "Initial commit: Kafka notification service"
git push
```

## Step 2: Add Docker Compose to the New Repo

Create `docker-compose.yml` in the new repo:

```yaml
services:
  notifications:
    build: .
    environment:
      NOTIFICATIONS_KAFKA_BOOTSTRAP_SERVERS: kafka:9092
      NOTIFICATIONS_KAFKA_TOPIC: post-events
      NOTIFICATIONS_KAFKA_CONSUMER_GROUP: notifications-service
    ports:
      - "8001:8001"
    restart: unless-stopped

networks:
  default:
    name: postways-v2_default
    external: true
```

The `external: true` network connects this service to the same Docker network where Kafka is already running from the Django project. No extra configuration needed — it can reach `kafka:9092` by container name.

## Step 3: Clean Up the Django Repo

Remove the service directory:

```bash
rm -rf services/notifications/
```

Remove the `notifications` service block from `docker/docker-compose.dev.yml`:

```yaml
  # DELETE this entire block:
  notifications:
    build:
      context: ../services/notifications
      dockerfile: Dockerfile
    environment:
      NOTIFICATIONS_KAFKA_BOOTSTRAP_SERVERS: kafka:9092
      NOTIFICATIONS_KAFKA_TOPIC: post-events
      NOTIFICATIONS_KAFKA_CONSUMER_GROUP: notifications-service
    ports:
      - "8001:8001"
    depends_on:
      kafka:
        condition: service_healthy
    restart: unless-stopped
```

Keep Kafka in the Django Docker Compose — it's the shared infrastructure.

## Step 4: Run Them Independently

```bash
# Terminal 1: Django + Kafka + other services
cd postways-v2
docker compose -f docker/docker-compose.dev.yml up

# Terminal 2: Notification service (joins the same Docker network)
cd postways-notifications
docker compose up --build
```

## Result

```
postways-v2/                    postways-notifications/
├── apps/diary/                 ├── app/
│   ├── kafka_producer.py       │   ├── main.py
│   └── views/api.py            │   ├── consumer.py
├── docker/                     │   ├── email.py
│   └── docker-compose.dev.yml  │   └── config.py
│       (Kafka lives here)      ├── Dockerfile
└── ...                         ├── pyproject.toml
                                └── docker-compose.yml

── Kafka topic "post-events" ──>
```

Two repos, two builds, two deploys, communicating only through Kafka.
