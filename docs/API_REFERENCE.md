# API Reference (Frontend Guide)

Base URL: `http://localhost:8000` (or your deployment URL)

## Authentication

All endpoints except `/auth/register`, `/auth/login`, and `/health` require:
```
Authorization: Bearer <jwt_token>
```

## Endpoints

### POST /auth/register
Create hunter profile.

**Request:**
```json
{
  "email": "hunter@example.com",
  "password": "secret",
  "display_name": "John Doe"
}
```

**Response:** `UserResponse` (id, email, display_name, created_at)

---

### POST /auth/login
Login, get JWT.

**Request:**
```json
{
  "email": "hunter@example.com",
  "password": "secret"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

---

### POST /hunt-teams
Create hunt team.

**Request:**
```json
{
  "name": "Team Alpha"
}
```

**Response:** HuntTeamResponse

---

### GET /hunt-teams
List my hunt teams.

**Response:** Array of HuntTeamResponse

---

### GET /hunt-teams/search?q=...
Search hunt teams by name (all teams, not only yours).

**Query:** `q` – search string (matched case-insensitively against team name).

**Response:** Array of HuntTeamSearchResult:
```json
[
  {
    "id": 1,
    "name": "Team Alpha",
    "created_by_user_id": 1,
    "created_at": "...",
    "is_member": true
  }
]
```
`is_member` is true if the current user is in that team.

---

### GET /hunt-teams/{id}
Get team with members and dog count.

**Response:** HuntTeamDetailResponse (includes members[], dog_count)

---

### POST /hunt-teams/{id}/join
Join hunt team (no body).

---

### DELETE /hunt-teams/{id}/members/{user_id}
Remove a member from the team. **Only the team owner** can call this.

**Path:** `id` = team id, `user_id` = user to remove.

**Errors:** 403 if caller is not owner; 400 if trying to remove the owner.

---

### POST /hunt-teams/{id}/dogs
Connect dog to team.

**Request:**
```json
{
  "client_id": "dog01"
}
```
(client_id = MQTT client ID from ESP32 tracker)

---

### GET /hunts/teams/{team_id}
List hunts for a team.

**Response:** Array of HuntResponse

---

### POST /hunts/teams/{team_id}/start
Start a hunt.

**Response:** HuntResponse

---

### POST /hunts/{id}/join
Join a hunt (start sharing position).

---

### POST /hunts/{id}/end
End an active hunt.

---

### GET /hunts/{id}
Get hunt with participants.

**Response:** HuntDetailResponse (includes participants[])

---

### POST /hunts/{id}/position
Report hunter position (from app/web GPS).

**Request:**
```json
{
  "lat": 59.33,
  "lon": 18.07,
  "alt": 12,
  "speed": 0.5,
  "accuracy": 5.0
}
```
(alt, speed, accuracy optional)

---

### GET /hunts/{id}/positions?since_minutes=60
Get positions (hunters + dogs). Default last 60 min.

**Response:**
```json
[
  {
    "source_type": "hunter",
    "source_id": "1",
    "lat": 59.33,
    "lon": 18.07,
    "alt": 12,
    "speed": 0.5,
    "accuracy": 5.0,
    "fix": true,
    "timestamp": "2025-03-01T12:00:00"
  },
  {
    "source_type": "dog",
    "source_id": "dog01",
    "lat": 59.34,
    "lon": 18.08,
    ...
  }
]
```

---

### WebSocket /hunts/{id}/live?token=JWT
Real-time feed. Connect with JWT in query param.

**Messages received:**
- `{"type": "position", "data": {...}}` - new position
- `{"type": "chat", "data": {...}}` - new chat message

**Client can send:** `"ping"` → receives `{"type": "pong"}`

---

### POST /hunt-teams/{id}/chat
Send chat message.

**Request:**
```json
{
  "content": "Hello team!"
}
```

---

### GET /hunt-teams/{id}/chat?limit=50&before_id=123
Chat history (paginated). `before_id` for cursor pagination.

---

### POST /notifications/register
Register device for push notifications.

**Request:**
```json
{
  "token": "fcm-or-apns-token",
  "platform": "android"
}
```
(platform: android | ios | web)
