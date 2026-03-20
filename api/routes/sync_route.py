from fastapi import APIRouter, Depends
from api.auth import require_token
router = APIRouter()

@router.post("/sync", dependencies=[Depends(require_token)])
async def trigger_sync():
    return {}
