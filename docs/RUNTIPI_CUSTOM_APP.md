# RunTipi "Create custom app" – correct setup

If you use **Create custom app** instead of the app store, use the ready-made compose that includes Postgres and a fixed DB password.

## Easiest: use the provided compose file

In the repo there is **`docker-compose.runtipi-custom.yml`** which already includes:

- **Postgres** with user `tracker`, password `tracker`, database `hundtracker`
- **Backend** with `DATABASE_URL` pointing at the Postgres service (`hundtracker-db`), so no hostname or DB password to configure

**Steps:**

1. Open `docker-compose.runtipi-custom.yml` in the repo (or copy it from below).
2. In RunTipi → **Create custom app** → paste the full contents of that file.
3. In RunTipi, add **one environment variable** for the backend service: **`MQTT_PASSWORD`** = (the password from your `mqtt settings.txt`).
4. (Optional) Add **`JWT_SECRET`** if you want your own secret; otherwise the compose uses a default for testing.
5. Save and start the app.

Postgres password is set **in the compose file** (`tracker`); you don’t set it in RunTipi. Only `MQTT_PASSWORD` (and optionally `JWT_SECRET`) need to be set in RunTipi’s env vars.

---

## Why not `localhost` for the database?

Each Docker container has its own `localhost`. The backend’s `localhost` is itself, not Postgres. So the compose uses the **service name** `hundtracker-db` as the database host; Docker resolves that to the Postgres container.

---

## Full compose (reference)

Contents of `docker-compose.runtipi-custom.yml`:

```yaml
services:
  hundtracker-backend:
    image: ghcr.io/mrgraxen/hundtracker-backend:latest
    environment:
      - DATABASE_URL=postgresql+asyncpg://tracker:tracker@hundtracker-db:5432/hundtracker
      - MQTT_HOST=mqtt.chickendinner.vip
      - MQTT_PORT=8883
      - MQTT_USERNAME=trackerbackend
      - MQTT_PASSWORD=${MQTT_PASSWORD}
      - JWT_SECRET=${JWT_SECRET:-change-me-use-env-in-production}
    depends_on:
      hundtracker-db:
        condition: service_healthy
    restart: unless-stopped

  hundtracker-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: tracker
      POSTGRES_PASSWORD: tracker
      POSTGRES_DB: hundtracker
    volumes:
      - hundtracker_db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tracker"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  hundtracker_db_data:
```

**Set in RunTipi (env vars for the app):** `MQTT_PASSWORD` (required). Optional: `JWT_SECRET`.
