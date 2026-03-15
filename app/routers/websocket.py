"""WebSocket endpoint for real-time hunt live feed."""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import oauth2_scheme
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Hunt, HuntParticipant, HuntTeamMember
from app.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


async def get_user_from_token(token: str) -> int | None:
    """Extract user_id from JWT. Returns None if invalid."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return int(payload.get("sub"))
    except (JWTError, ValueError):
        return None


@router.websocket("/hunts/{hunt_id}/live")
async def hunt_live(
    websocket: WebSocket,
    hunt_id: int,
    token: str = Query(..., description="JWT Bearer token"),
):
    """Real-time feed: positions + chat for this hunt.
    Connect with ?token=<jwt>. Receives { type: 'position'|'chat', data: {...} }
    """
    user_id = await get_user_from_token(token)
    if not user_id:
        await websocket.close(code=4001)
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Hunt).where(Hunt.id == hunt_id))
        hunt = result.scalar_one_or_none()
        if not hunt:
            await websocket.close(code=4004)
            return

        member = await db.execute(
            select(HuntTeamMember).where(
                HuntTeamMember.hunt_team_id == hunt.hunt_team_id,
                HuntTeamMember.user_id == user_id,
            )
        )
        if not member.scalar_one_or_none():
            await websocket.close(code=4003)
            return

    await manager.connect(hunt_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Client can send ping or commands - for now we ignore
            # Could add: position report, chat send (or use REST for those)
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(hunt_id, websocket)
