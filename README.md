# Hundtracker Backend

Backend for a hunter tracker app: hunt teams, dog positions (ESP32/MQTT), hunter positions (app/web), and chat.

**New to GitHub or CI/CD?** See [docs/GITHUB_SETUP.md](docs/GITHUB_SETUP.md) for step-by-step setup and pushing this repo.

## Features

- **Hunter profiles** – Register; login returns JWT plus user profile (`id`, `display_name`, `created_at`)
- **Hunt teams** – Create or join teams; hunters can belong to multiple teams
- **Dogs** – Connect dogs (MQTT client_id) to hunt teams; positions from ESP32 via MQTT
- **Hunts** – Start a hunt; hunters join and share positions; see map with hunters + dogs
- **Chat** – Team chat (persisted for offline), real-time via MQTT + WebSocket
- **Push notifications** – Register device tokens; integration points for FCM/APNs (see [docs/NOTIFICATIONS.md](docs/NOTIFICATIONS.md))

## Architecture

- **FastAPI** – REST API + WebSocket
- **PostgreSQL** – Persistent storage
- **MQTT** – Dog positions (subscribe `position/in/+` and `/position/in/+`), chat publish (`/huntteam/{id}/chat`)
- **Docker** – Backend + PostgreSQL in containers

## Requirements

- Docker & Docker Compose (or Python 3.11+ for local development)
- MQTT broker access (see `mqtt settings.env` – not in repo, keep local)

## Quick Start

1. Copy `.env.example` to `.env` and set:
   - `MQTT_PASSWORD` (from your `mqtt settings.env`)
   - `JWT_SECRET` (e.g. `openssl rand -hex 32`)

2. Run with Docker Compose:

```bash
docker-compose up -d
```

3. API docs: http://localhost:8000/docs

4. Health check: `GET /health`

## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create hunter profile |
| POST | `/auth/login` | Login; JWT + user profile (no extra call) |
| GET | `/hunt-teams` | List my hunt teams |
| GET | `/hunt-teams/search?q=...` | Search teams by name |
| POST | `/hunt-teams` | Create hunt team |
| GET | `/hunt-teams/{id}` | Get team with members, dog count |
| POST | `/hunt-teams/{id}/join` | Join hunt team |
| DELETE | `/hunt-teams/{id}/members/{user_id}` | Remove member (owner only) |
| POST | `/hunt-teams/{id}/dogs` | Connect dog (client_id) to team |
| GET | `/hunts/teams/{team_id}` | List hunts for team |
| POST | `/hunts/teams/{team_id}/start` | Start a hunt |
| POST | `/hunts/{id}/join` | Join hunt (share position) |
| GET | `/hunts/{id}` | Get hunt with participants |
| POST | `/hunts/{id}/position` | Report hunter position |
| GET | `/hunts/{id}/positions` | Get positions (hunters + dogs) |
| WS | `/hunts/{id}/live?token=JWT` | Real-time positions + chat |
| POST | `/hunt-teams/{id}/chat` | Send chat message |
| GET | `/hunt-teams/{id}/chat` | Chat history (paginated) |
| POST | `/hunts/{id}/end` | End active hunt |
| POST | `/notifications/register` | Register device for push |

### Login response (`POST /auth/login`)

Returns the access token and the authenticated user so the client can cache profile fields without decoding the JWT:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user": {
    "id": 42,
    "email": "hunter@example.com",
    "display_name": "Erik",
    "created_at": "2024-01-01T00:00:00"
  }
}
```

## MQTT

**Troubleshooting:** `MQTT_SUBSCRIBE_CATCHALL` defaults to **true** for now (subscribe to `#`, log on `/debug/mqtt`). Set **`false`** before production.

### Dog Positions (subscribe)

- **Topic**: `position/in/{clientid}` or `/position/in/{clientid}` — leading `/` is a **different** topic string; backend subscribes to **both** patterns.
- **Payload (with GPS fix)**:
  ```json
  {"client":"dog01","lat":59.329323,"lon":18.068581,"speed":0.0,"alt":12,"vsat":8,"accuracy":3.5,"time":"2025-03-01T15:22:10"}
  ```
- **Payload (no GPS fix)**:
  ```json
  {"client":"dog01","fix":false,"nogps":true}
  ```

### Chat (publish)

- **Topic**: `/huntteam/{team_id}/chat`
- **Payload**:
  ```json
  {"user_id":1,"display_name":"Hunter1","content":"Hello","timestamp":"2025-03-01T12:00:00"}
  ```

## Frontend Integration

1. **Auth** – On login, store `access_token` and optional `user` from the response; send `Authorization: Bearer {token}` on later requests
2. **Map** – Poll `GET /hunts/{id}/positions` or use WebSocket `/hunts/{id}/live?token=JWT` for real-time
3. **Hunter position** – POST to `/hunts/{id}/position` (GPS from device)
4. **Chat** – GET history, POST new messages; subscribe to MQTT or use WebSocket for real-time
5. **Push** – Register device token at login via `POST /notifications/register`

## Development

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
# Set DATABASE_URL, MQTT_*, JWT_SECRET in .env
uvicorn app.main:app --reload
```

## Deploy to GitHub Container Registry (GHCR) and RunTipi

### Publish image to GHCR

1. Push this repo to GitHub (e.g. `main` or `master`).
2. The **GitHub Actions** workflow (`.github/workflows/publish-ghcr.yml`) runs on push and builds the Docker image, then pushes it to:
   ```text
   ghcr.io/<your-github-username>/hundtracker-backend:latest
   ```
3. (Optional) Make the package public: **Repo → Packages → hundtracker-backend → Package settings → Change visibility**.

### Install on RunTipi from GHCR

**Option A – Use this repo as a custom app store**

1. Ensure the repo has the **apps** folder (RunTipi expects `apps/<app-id>/` at the repo root).
2. In RunTipi: **Settings → App Stores → Add App Store** → enter your repo URL, e.g. `https://github.com/YOUR_USERNAME/Hundtrakcer-backend`.
3. Click **Update App Stores**, then install **Hundtracker Backend**.
4. In the app config, set **Docker image** to `ghcr.io/YOUR_USERNAME/hundtracker-backend:latest` and fill **MQTT password**, **JWT secret** (or use generated values), and optional MQTT host/port/username.

**Option B – Create custom app in RunTipi**

1. In RunTipi: **Create custom app**.
2. Use a compose that uses the image from GHCR and the same env vars (e.g. copy from `apps/hundtracker/docker-compose.yml` and set the image to your GHCR URL).

Add a logo at `apps/hundtracker/metadata/logo.jpg` (512×512 px) so the app store shows an icon.

## Long-term Considerations

- **Position retention** – Positions accumulate; consider cleanup job or time-series DB (TimescaleDB)
- **Scale** – MQTT listener is single-instance; for horizontal scaling, use shared MQTT consumer group or Redis pub/sub
- **Security** – Set CORS `allow_origins` for production; rotate JWT_SECRET; use TLS for DB
