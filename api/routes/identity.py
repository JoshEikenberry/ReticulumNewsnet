from fastapi import APIRouter, Depends
from api.auth import require_token
router = APIRouter()

@router.get("/identity", dependencies=[Depends(require_token)])
async def get_identity():
    return {}
