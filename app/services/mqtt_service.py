"""MQTT service - subscribes to dog positions, publishes chat.

Subscribes to: /position/in/+ (all dog positions per mqtt examples)
Publishes to: /huntteam/{team_id}/chat (chat messages from API)
"""
import asyncio
import json
import logging
import ssl
from datetime import datetime
from typing import Callable

import aiomqtt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.mqtt_debug_buffer import maybe_append_mqtt_debug
from app.models import Dog, DogHuntTeam, Hunt, HuntStatus, Position, SourceType

logger = logging.getLogger(__name__)

# Topic patterns (from mqtt examples)
POSITION_TOPIC_PREFIX = "/position/in/"
CHAT_TOPIC_PREFIX = "/huntteam/"


async def _process_dog_position(
    client_id: str, payload: dict, topic_str: str = ""
) -> None:
    """Store dog position in DB and associate with active hunts."""
    maybe_append_mqtt_debug(
        {
            "phase": "mqtt_received",
            "client_id": client_id,
            "topic": topic_str,
            "detail": {
                "payload_keys": list(payload.keys()),
                "payload_preview": str(payload)[:800],
            },
        }
    )
    async with AsyncSessionLocal() as session:
        try:
            # Ensure dog exists
            result = await session.execute(
                select(Dog).where(Dog.client_id == client_id)
            )
            dog = result.scalar_one_or_none()
            if not dog:
                # Create dog on first position (dogs don't have credentials)
                dog = Dog(client_id=client_id)
                session.add(dog)
                await session.flush()

            # Find active hunts for teams that have this dog
            hunt_result = await session.execute(
                select(Hunt.id)
                .join(DogHuntTeam, DogHuntTeam.hunt_team_id == Hunt.hunt_team_id)
                .join(Dog, Dog.id == DogHuntTeam.dog_id)
                .where(Dog.client_id == client_id)
                .where(Hunt.status == HuntStatus.ACTIVE)
            )
            active_hunt_ids = [r[0] for r in hunt_result.all()]
            hunt_id = active_hunt_ids[0] if active_hunt_ids else None

            team_rows = await session.execute(
                select(DogHuntTeam.hunt_team_id)
                .where(DogHuntTeam.dog_id == dog.id)
                .order_by(DogHuntTeam.hunt_team_id)
            )
            dog_team_ids = [r[0] for r in team_rows.all()]

            # Parse payload (from mqtt examples)
            fix = payload.get("fix", True)
            if payload.get("nogps") or fix is False:
                # No GPS fix - store minimal record
                ts_str = payload.get("time") or datetime.utcnow().isoformat()
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    ts = datetime.utcnow()
                pos = Position(
                    source_type=SourceType.DOG,
                    source_id=client_id,
                    hunt_id=hunt_id,
                    lat=None,
                    lon=None,
                    fix=False,
                    timestamp=ts,
                )
            else:
                ts_str = payload.get("time") or datetime.utcnow().isoformat()
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    ts = datetime.utcnow()
                pos = Position(
                    source_type=SourceType.DOG,
                    source_id=client_id,
                    hunt_id=hunt_id,
                    lat=payload.get("lat"),
                    lon=payload.get("lon"),
                    alt=payload.get("alt"),
                    speed=payload.get("speed"),
                    accuracy=payload.get("accuracy"),
                    fix=True,
                    timestamp=ts,
                )
            session.add(pos)
            await session.commit()
            await session.refresh(pos)
            logger.debug("Stored position for dog %s", client_id)

            ws_ok: list[int] = []
            ws_err: str | None = None
            # Broadcast to WebSocket clients for active hunts
            if active_hunt_ids:
                try:
                    from app.websocket_manager import manager
                    pos_dict = {
                        "source_type": "dog",
                        "source_id": client_id,
                        "lat": pos.lat,
                        "lon": pos.lon,
                        "alt": pos.alt,
                        "speed": pos.speed,
                        "accuracy": pos.accuracy,
                        "fix": pos.fix,
                        "timestamp": pos.timestamp.isoformat(),
                    }
                    for hid in active_hunt_ids:
                        await manager.broadcast_position(hid, pos_dict)
                        ws_ok.append(hid)
                except Exception as e:
                    ws_err = str(e)
                    logger.warning("WebSocket broadcast failed: %s", e)

            maybe_append_mqtt_debug(
                {
                    "phase": "mqtt_processed",
                    "client_id": client_id,
                    "topic": topic_str,
                    "detail": {
                        "dog_db_id": dog.id,
                        "dog_linked_team_ids": dog_team_ids,
                        "active_hunt_ids": active_hunt_ids,
                        "position_id": pos.id,
                        "position_hunt_id": hunt_id,
                        "fix": pos.fix,
                        "lat": pos.lat,
                        "lon": pos.lon,
                        "websocket_broadcast_hunt_ids": ws_ok,
                        "websocket_error": ws_err,
                    },
                }
            )
        except Exception as e:
            await session.rollback()
            logger.exception("Failed to store dog position: %s", e)
            maybe_append_mqtt_debug(
                {
                    "phase": "mqtt_error",
                    "client_id": client_id,
                    "topic": topic_str,
                    "error": repr(e),
                    "detail": {},
                }
            )


async def run_mqtt_listener(
    on_position: Callable[[str, dict], None] | None = None,
) -> None:
    """Run MQTT listener - subscribes to positions, runs until cancelled."""
    settings = get_settings()
    ctx = ssl.create_default_context()

    while True:
        try:
            async with aiomqtt.Client(
                hostname=settings.mqtt_host,
                port=settings.mqtt_port,
                username=settings.mqtt_username,
                password=settings.mqtt_password,
                tls_context=ctx,
            ) as client:
                topic = f"{POSITION_TOPIC_PREFIX}+"
                await client.subscribe(topic)
                logger.info("MQTT subscribed to %s", topic)

                async for message in client.messages:
                    try:
                        if not message.topic.matches(f"{POSITION_TOPIC_PREFIX}+"):
                            continue
                        topic_str = str(getattr(message.topic, "value", message.topic))
                        client_id = topic_str.rstrip("/").split("/")[-1]
                        payload = json.loads(message.payload.decode())
                        await _process_dog_position(client_id, payload, topic_str)
                        if on_position:
                            on_position(client_id, payload)
                    except json.JSONDecodeError as e:
                        logger.warning("Invalid JSON from %s: %s", message.topic, e)
                        topic_str = str(getattr(message.topic, "value", message.topic))
                        maybe_append_mqtt_debug(
                            {
                                "phase": "mqtt_json_error",
                                "client_id": topic_str.rstrip("/").split("/")[-1],
                                "topic": topic_str,
                                "error": str(e),
                                "detail": {},
                            }
                        )
                    except Exception as e:
                        logger.exception("Error processing position: %s", e)
        except asyncio.CancelledError:
            logger.info("MQTT listener cancelled")
            break
        except Exception as e:
            logger.exception("MQTT connection error, reconnecting in 10s: %s", e)
            await asyncio.sleep(10)


async def publish_chat(team_id: int, user_id: int, display_name: str, content: str) -> None:
    """Publish chat message to MQTT for real-time delivery to subscribers."""
    settings = get_settings()
    ctx = ssl.create_default_context()
    topic = f"{CHAT_TOPIC_PREFIX}{team_id}/chat"
    payload = json.dumps({
        "user_id": user_id,
        "display_name": display_name,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    })
    try:
        async with aiomqtt.Client(
            hostname=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_username,
            password=settings.mqtt_password,
            tls_context=ctx,
        ) as client:
            await client.publish(topic, payload, qos=1)
            logger.debug("Published chat to %s", topic)
    except Exception as e:
        logger.exception("Failed to publish chat to MQTT: %s", e)
