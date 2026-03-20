from __future__ import annotations
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from api.auth import require_token

router = APIRouter()


class PostArticleBody(BaseModel):
    newsgroup: str
    subject: str
    body: str
    references: list[str] = []


def _serialize_article(a: dict) -> dict:
    return {
        "message_id": a["message_id"],
        "newsgroup": a["newsgroup"],
        "subject": a["subject"],
        "body": a["body"],
        "author_hash": a["author_hash"],
        "display_name": a["display_name"],
        "timestamp": a["timestamp"],
        "references": json.loads(a["references"]) if isinstance(a.get("references"), str) else (a.get("references") or []),
        "received_at": a["received_at"],
    }


@router.get("/articles", dependencies=[Depends(require_token)])
async def list_articles(request: Request, group: Optional[str] = None, after: Optional[float] = None):
    articles = request.app.state.node.store.list_articles(newsgroup=group)
    if after is not None:
        articles = [a for a in articles if a["timestamp"] > after]
    return [_serialize_article(a) for a in articles]


@router.get("/articles/{message_id}", dependencies=[Depends(require_token)])
async def get_article(message_id: str, request: Request):
    article = request.app.state.node.store.get_article(message_id)
    if article is None:
        raise HTTPException(status_code=404, detail={"error": "not found"})
    # Fetch thread (same newsgroup, same thread root)
    newsgroup = article["newsgroup"]
    all_in_group = request.app.state.node.store.list_articles(newsgroup=newsgroup)
    serialized = _serialize_article(article)
    serialized["thread"] = [_serialize_article(a) for a in all_in_group]
    return serialized


@router.post("/articles", dependencies=[Depends(require_token)], status_code=201)
async def post_article(body: PostArticleBody, request: Request):
    node = request.app.state.node
    article = node.post(
        newsgroup=body.newsgroup,
        subject=body.subject,
        body=body.body,
        references=body.references,
    )
    await request.app.state.hub.broadcast({
        "type": "new_article",
        "article": {"message_id": article.message_id, "newsgroup": body.newsgroup},
    })
    return {"message_id": article.message_id}
