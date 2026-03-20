from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from api.auth import require_token

router = APIRouter()


class AddPeerBody(BaseModel):
    address: str


@router.get("/peers", dependencies=[Depends(require_token)])
async def list_peers(request: Request):
    node = request.app.state.node
    rns_peers = node.store.list_peers()
    tcp_peers = node.list_tcp_peers()
    return {
        "rns_peers": [
            {
                "destination_hash": p["destination_hash"],
                "display_name": p.get("display_name"),
                "last_seen": p.get("last_seen"),
                "last_synced": p.get("last_synced"),
            }
            for p in rns_peers
        ],
        "tcp_peers": tcp_peers,
    }


@router.post("/peers", dependencies=[Depends(require_token)], status_code=201)
async def add_peer(body: AddPeerBody, request: Request):
    try:
        normalized = request.app.state.node.add_tcp_peer(body.address)
        return {"address": normalized}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": str(e)})


@router.delete("/peers/{address:path}", dependencies=[Depends(require_token)])
async def remove_peer(address: str, request: Request):
    request.app.state.node.remove_tcp_peer(address)
    return {"removed": address}
