from fastapi import APIRouter, Depends
from api.auth import require_token
router = APIRouter()

@router.get("/filters", dependencies=[Depends(require_token)])
async def list_filters():
    return []
