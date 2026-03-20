from fastapi import APIRouter, Depends
from api.auth import require_token
router = APIRouter()

@router.get("/config", dependencies=[Depends(require_token)])
async def get_config():
    return {}
