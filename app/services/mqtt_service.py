"""MQTT service - subscribes to dog positions, publishes chat.

Subscribes to: position/in/+ AND /position/in/+ (with/without leading slash — MQTT treats them as different topics)
Publishes to: /huntteam/{team_id}/chat (chat messages from API)
"""
import asyncio
import json
import logging
import re
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

# Dog position topics — subscribe to both; brokers/clients may use either string.
POSITION_SUBSCRIBE_PATTERNS: tuple[str, ...] = ("position/in/+", "/position/in/+")
CHAT_TOPIC_PREFIX = "/huntteam/"

# Match .../position/in/{client_id} or position/in/{client_id} (with optional leading /)
_POSITION_TOPIC_CLIENT = re.compile(r"(?:^|/)position/in/([^/]+)$")


def _client_id_from_position_topic(topic_str: str) -> str | None:
    m = _POSITION_TOPIC_CLIENT.search(topic_str)
    return m.group(1) if m else None


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
                if settings.mqtt_subscribe_catchall:
                    patterns = ("#",)
                    logger.warning(
                        "MQTT catch-all subscription enabled (#) — high volume; disable MQTT_SUBSCRIBE_CATCHALL after testing"
                    )
                else:
                    patterns = POSITION_SUBSCRIBE_PATTERNS
                for pat in patterns:
                    await client.subscribe(pat)
                    logger.info("MQTT subscribed to %s", pat)
                maybe_append_mqtt_debug(
                    {
                        "phase": "mqtt_listener_ready",
                        "client_id": "",
                        "topic": ",".join(patterns),
                        "detail": {
                            "broker": settings.mqtt_host,
                            "port": settings.mqtt_port,
                            "subscribe_patterns": list(patterns),
                            "catchall": settings.mqtt_subscribe_catchall,
                            "username": settings.mqtt_username,
                            "password_set": bool(settings.mqtt_password),
                        },
                    }
                )

                async for message in client.messages:
                    try:
                        topic_str = str(getattr(message.topic, "value", message.topic))
                        raw = message.payload
                        preview = ""
                        try:
                            preview = raw.decode()[:1200]
                        except Exception:
                            preview = f"<non-utf8 binary, {len(raw)} bytes>"

                        if settings.mqtt_subscribe_catchall:
                            maybe_append_mqtt_debug(
                                {
                                    "phase": "mqtt_catchall",
                                    "client_id": "",
                                    "topic": topic_str,
                                    "detail": {
                                        "payload_preview": preview,
                                        "will_process_as_position": bool(
                                            _client_id_from_position_topic(topic_str)
                                        ),
                                    },
                                }
                            )

                        client_id = _client_id_from_position_topic(topic_str)
                        if client_id is None:
                            continue

                        payload = json.loads(raw.decode())
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
                        topic_str = ""
                        try:
                            topic_str = str(
                                getattr(message.topic, "value", message.topic)
                            )
                        except Exception:
                            pass
                        maybe_append_mqtt_debug(
                            {
                                "phase": "mqtt_message_handler_error",
                                "client_id": topic_str.rstrip("/").split("/")[-1]
                                if topic_str
                                else "",
                                "topic": topic_str,
                                "error": repr(e),
                                "detail": {},
                            }
                        )
        except asyncio.CancelledError:
            logger.info("MQTT listener cancelled")
            break
        except Exception as e:
            logger.exception("MQTT connection error, reconnecting in 10s: %s", e)
            maybe_append_mqtt_debug(
                {
                    "phase": "mqtt_listener_connect_error",
                    "client_id": "",
                    "topic": "",
                    "error": repr(e),
                    "detail": {
                        "broker": settings.mqtt_host,
                        "port": settings.mqtt_port,
                        "username": settings.mqtt_username,
                        "password_set": bool(settings.mqtt_password),
                    },
                }
            )
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
