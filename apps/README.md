# RunTipi app store (apps)

This folder is the **RunTipi app store** layout. When you use this repo as a custom app store in RunTipi, it looks for apps here.

## Logo

RunTipi expects a logo per app. Add:

`hundtracker/metadata/logo.jpg`

Use a 512×512 px (or any 1:1) image. Without it, the app may still install but the store might show a placeholder.

## Adding this repo as an app store in RunTipi

1. Push this repo to GitHub and publish the backend image to GHCR (see main README).
2. In RunTipi: **Settings → App Stores → Add App Store**.
3. Enter this repo URL: `https://github.com/YOUR_USERNAME/YOUR_REPO_NAME`
4. Click **Update App Stores**, then install **Hundtracker Backend** from the list.
5. Set **Docker image** to your GHCR image (e.g. `ghcr.io/YOUR_USERNAME/hundtracker-backend:latest`) and fill MQTT password, JWT secret, and optional MQTT host/port/username.
