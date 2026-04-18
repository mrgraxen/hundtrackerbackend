"""Development-only MQTT debug page (no auth). Enable with ENABLE_MQTT_DEBUG_PAGE=true."""
from html import escape
from json import dumps as json_dumps

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.mqtt_debug_buffer import clear_events, get_events

router = APIRouter(tags=["debug"])


def _render_html() -> str:
    events = get_events()
    rows = []
    for ev in events:
        ts = escape(str(ev.get("ts", "")))
        phase = escape(str(ev.get("phase", "")))
        client_id = escape(str(ev.get("client_id", "")))
        topic = escape(str(ev.get("topic", "")))
        detail = escape(json_dumps(ev.get("detail", {}), ensure_ascii=False, default=str)[:4000])
        err = ev.get("error")
        err_html = f'<pre style="color:red">{escape(str(err))}</pre>' if err else ""
        rows.append(
            f"<tr><td style='vertical-align:top;white-space:nowrap'>{ts}</td>"
            f"<td style='vertical-align:top'><b>{phase}</b><br/>client_id={client_id}<br/>topic={topic}"
            f"{err_html}</td>"
            f"<td style='vertical-align:top'><pre style='margin:0;white-space:pre-wrap'>{detail}</pre></td></tr>"
        )
    body = "\n".join(rows) if rows else "<tr><td colspan='3'>No MQTT position events yet.</td></tr>"
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><title>MQTT position debug</title>
<meta http-equiv="refresh" content="4"/>
<style>
body {{ font-family: system-ui, sans-serif; margin: 12px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
td, th {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
th {{ background: #f0f0f0; }}
.warning {{ background: #fff3cd; padding: 10px; margin-bottom: 12px; }}
</style></head>
<body>
<div class="warning"><b>Development only.</b> Disable <code>ENABLE_MQTT_DEBUG_PAGE</code> before production.
<a href="?clear=1">Clear buffer</a></div>
<table><thead><tr><th>Time (UTC)</th><th>Phase</th><th>Detail</th></tr></thead>
<tbody>{body}</tbody></table>
<p><small>Auto-refresh every 4s. Last {len(events)} events (max 300).</small></p>
</body></html>"""


@router.get("/debug/mqtt", response_class=HTMLResponse)
async def mqtt_debug_page(
    clear: str | None = Query(None, description="Pass clear=1 to empty the buffer"),
):
    settings = get_settings()
    if not settings.enable_mqtt_debug_page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if clear == "1":
        clear_events()
    return HTMLResponse(content=_render_html())


@router.get("/debug/mqtt/events")
async def mqtt_debug_events_json():
    """JSON dump of the same buffer (still gated by enable flag)."""
    settings = get_settings()
    if not settings.enable_mqtt_debug_page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return {"events": get_events()}
