from __future__ import annotations
from fastapi import APIRouter, Depends, Request
from api.auth import require_token

router = APIRouter()


@router.get("/groups", dependencies=[Depends(require_token)])
async def list_groups(request: Request):
    return request.app.state.node.store.list_newsgroups()
