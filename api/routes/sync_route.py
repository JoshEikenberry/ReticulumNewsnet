from __future__ import annotations
import threading
from fastapi import APIRouter, Depends, Request
from api.auth import require_token

router = APIRouter()


@router.post("/sync", dependencies=[Depends(require_token)])
async def trigger_sync(request: Request):
    node = request.app.state.node
    # Run in background thread — sync is blocking
    count_result = {"count": 0}

    def _do_sync():
        count_result["count"] = node.sync_all_peers()

    t = threading.Thread(target=_do_sync, daemon=True)
    t.start()
    t.join(timeout=2)  # Wait briefly so we can return a count for quick syncs
    return {"synced_peers": count_result["count"], "status": "triggered"}
