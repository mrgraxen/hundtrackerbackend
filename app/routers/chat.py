"""Chat endpoints - send, history."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.models import Hunt, HuntStatus
from app.database import get_db
from app.models import ChatMessage, HuntTeamMember, User
from app.schemas import ChatMessageCreate, ChatMessageResponse
from app.services.mqtt_service import publish_chat

router = APIRouter(prefix="/hunt-teams", tags=["chat"])


async def _require_team_member(db: AsyncSession, team_id: int, user_id: int) -> None:
    result = await db.execute(
        select(HuntTeamMember).where(
            HuntTeamMember.hunt_team_id == team_id,
            HuntTeamMember.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this hunt team",
        )


@router.post("/{team_id}/chat", response_model=ChatMessageResponse)
async def send_chat(
    team_id: int,
    data: ChatMessageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send chat message. Stored in DB, published to MQTT for real-time."""
    await _require_team_member(db, team_id, user.id)

    msg = ChatMessage(
        hunt_team_id=team_id,
        user_id=user.id,
        content=data.content.strip(),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    display_name = user.display_name or user.email
    await publish_chat(team_id, user.id, display_name, msg.content)

    # Broadcast to WebSocket clients in active hunts for this team
    hunt_result = await db.execute(
        select(Hunt.id).where(
            Hunt.hunt_team_id == team_id,
            Hunt.status == HuntStatus.ACTIVE,
        )
    )
    hunt_ids = [r[0] for r in hunt_result.all()]
    if hunt_ids:
        try:
            from app.websocket_manager import manager
            await manager.broadcast_to_hunts(
                hunt_ids, "chat", {
                    "id": msg.id,
                    "user_id": msg.user_id,
                    "display_name": display_name,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                }
            )
        except Exception:
            pass

    # TODO: Trigger push notifications to team members (FCM/APNs)
    # See docs/NOTIFICATIONS.md for integration points

    return ChatMessageResponse(
        id=msg.id,
        hunt_team_id=msg.hunt_team_id,
        user_id=msg.user_id,
        display_name=display_name,
        content=msg.content,
        created_at=msg.created_at,
    )


@router.get("/{team_id}/chat", response_model=list[ChatMessageResponse])
async def get_chat_history(
    team_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    before_id: int | None = Query(None, description="Cursor: messages before this ID"),
):
    """Get chat history - available when offline. Paginated."""
    await _require_team_member(db, team_id, user.id)

    q = (
        select(ChatMessage, User.display_name, User.email)
        .join(User, User.id == ChatMessage.user_id)
        .where(ChatMessage.hunt_team_id == team_id)
    )
    if before_id:
        q = q.where(ChatMessage.id < before_id)
    q = q.order_by(ChatMessage.id.desc()).limit(limit)

    result = await db.execute(q)
    rows = result.all()

    return [
        ChatMessageResponse(
            id=msg.id,
            hunt_team_id=msg.hunt_team_id,
            user_id=msg.user_id,
            display_name=display_name or email,
            content=msg.content,
            created_at=msg.created_at,
        )
        for msg, display_name, email in rows
    ]
