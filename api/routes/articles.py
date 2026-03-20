from fastapi import APIRouter, Depends
from api.auth import require_token
router = APIRouter()

@router.get("/articles", dependencies=[Depends(require_token)])
async def list_articles():
    return []
