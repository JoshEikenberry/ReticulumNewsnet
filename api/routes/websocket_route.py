from __future__ import annotations
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # Auth: token in query param
    token = ws.query_params.get("token", "")
    expected = ws.app.state.config.api_token
    if not expected or token != expected:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    hub = ws.app.state.hub
    await hub.connect(ws)
    try:
        while True:
            # Keep connection alive; server pushes events, client sends nothing
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(ws)
