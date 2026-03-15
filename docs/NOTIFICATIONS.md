# Push Notifications Integration

Chat messages should trigger app/web notifications when the user is not logged in. This document describes the integration points.

## Current Behavior

- Chat messages are stored in DB (always available via REST)
- Chat is published to MQTT (`/huntteam/{team_id}/chat`) for real-time delivery
- Chat is broadcast to WebSocket clients connected to active hunts
- Device tokens are registered via `POST /notifications/register`

## Integration Point: Push Notifications

When a chat message is sent (`POST /hunt-teams/{team_id}/chat`), the backend should:

1. Store the message (done)
2. Publish to MQTT (done)
3. Broadcast to WebSocket (done)
4. **Trigger push notifications** (TODO)

To implement push notifications:

1. **Fetch device tokens** for all hunt team members (except the sender)
2. **Send push** via Firebase Cloud Messaging (FCM) for Android/Web, or APNs for iOS

### Example Integration (FCM)

```python
# In app/routers/chat.py, after storing and publishing chat:
async def trigger_chat_notifications(db, team_id, sender_user_id, message_preview):
    result = await db.execute(
        select(DeviceToken)
        .where(DeviceToken.user_id.in_(
            select(HuntTeamMember.user_id).where(
                HuntTeamMember.hunt_team_id == team_id,
                HuntTeamMember.user_id != sender_user_id,
            )
        ))
    )
    tokens = result.scalars().all()
    for t in tokens:
        if t.platform == "android" or t.platform == "web":
            # Call FCM API
            pass
        elif t.platform == "ios":
            # Call APNs
            pass
```

### Recommended Libraries

- **FCM**: `firebase-admin` (Python)
- **APNs**: `apns2` or `aioapns`

## Frontend Requirements

- Register device token after login via `POST /notifications/register`
- Include `token` (FCM/APNs token) and `platform` (android|ios|web)
