# Hundtracker Backend

Backend API for the Hundtracker hunter tracker app.

## Features

- **Hunter profiles** – Register and login (JWT)
- **Hunt teams** – Create or join teams; search teams by name
- **Dogs** – Connect dogs (ESP32 MQTT client ID) to teams
- **Hunts** – Start a hunt; hunters join and share positions on a map
- **Chat** – Team chat (persisted, real-time via MQTT/WebSocket)
- **Positions** – Dog positions from MQTT; hunter positions from app

## Requirements

- MQTT broker (host, port, username, password) – e.g. from your tracker provider
- JWT secret – generated at install or set your own

## After install

- API: open the app URL (RunTipi will assign a port or domain)
- Docs: `https://YOUR_APP_URL/docs`
- Health: `GET /health`

## Image

The app uses a Docker image from GitHub Container Registry (GHCR). Set the **Docker image** field to your image, e.g.:

`ghcr.io/YOUR_GITHUB_USERNAME/hundtracker-backend:latest`

Push the image to GHCR using the GitHub Actions workflow in the repo (on push to `main`).
