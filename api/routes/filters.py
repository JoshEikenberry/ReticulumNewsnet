from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from api.auth import require_token

router = APIRouter()


class AddFilterBody(BaseModel):
    type: str   # "author", "newsgroup", "word"
    mode: str   # "blacklist", "whitelist"
    pattern: str


@router.get("/filters", dependencies=[Depends(require_token)])
async def list_filters(request: Request):
    return request.app.state.node.filter_store.list_filters()


@router.post("/filters", dependencies=[Depends(require_token)], status_code=201)
async def add_filter(body: AddFilterBody, request: Request):
    valid_types = {"author", "newsgroup", "word"}
    valid_modes = {"blacklist", "whitelist"}
    if body.type not in valid_types:
        raise HTTPException(422, {"error": f"type must be one of {valid_types}"})
    if body.mode not in valid_modes:
        raise HTTPException(422, {"error": f"mode must be one of {valid_modes}"})
    request.app.state.node.filter_store.add_filter(body.type, body.mode, body.pattern)
    return {"added": True}


@router.delete("/filters/{filter_id}", dependencies=[Depends(require_token)])
async def remove_filter(filter_id: str, request: Request):
    # filter_id is "type:mode:pattern" encoded as URL-safe string
    # Delegate to filter_store
    try:
        filter_type, mode, pattern = filter_id.split(":", 2)
        request.app.state.node.filter_store.remove_filter(filter_type, mode, pattern)
        return {"removed": True}
    except ValueError:
        raise HTTPException(400, {"error": "invalid filter id format — use type:mode:pattern"})
