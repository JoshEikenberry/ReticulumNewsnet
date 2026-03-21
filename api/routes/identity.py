from __future__ import annotations
import socket
from fastapi import APIRouter, Depends, Request
from api.auth import require_token
from newsnet.identity_words import hash_to_words

router = APIRouter()


@router.get("/identity", dependencies=[Depends(require_token)])
async def get_identity(request: Request):
    node = request.app.state.node
    cfg = request.app.state.config
    identity = node._identity_mgr.identity
    identity_hash = identity.hash.hex() if identity.hash else ""
    identity_words = hash_to_words(identity.get_public_key())

    # tcp_address: only meaningful if not bound to localhost
    tcp_address = None
    if cfg.api_host not in ("127.0.0.1", "localhost", "::1"):
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
            tcp_address = f"{local_ip}:{cfg.api_port}"
        except Exception:
            pass

    return {
        "identity_hash": identity_hash,
        "identity_words": identity_words,
        "display_name": cfg.display_name,
        "tcp_address": tcp_address,
    }
