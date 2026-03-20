from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request, status
from api.auth import require_token

router = APIRouter()

_IMMEDIATE_FIELDS = {"display_name", "retention_hours", "sync_interval_minutes", "strict_filtering"}
_RESTART_FIELDS = {"api_host", "api_port"}
_VALID_TYPES = {
    "display_name": str,
    "retention_hours": int,
    "sync_interval_minutes": int,
    "strict_filtering": bool,
    "api_host": str,
    "api_port": int,
}
_BOUNDS = {
    "retention_hours": (1, 720),
    "sync_interval_minutes": (1, None),
    "api_port": (1, 65535),
}


@router.get("/config", dependencies=[Depends(require_token)])
async def get_config(request: Request):
    cfg = request.app.state.config
    return {
        "display_name": cfg.display_name,
        "retention_hours": cfg.retention_hours,
        "sync_interval_minutes": cfg.sync_interval_minutes,
        "strict_filtering": cfg.strict_filtering,
        "api_host": cfg.api_host,
        "api_port": cfg.api_port,
    }


@router.patch("/config", dependencies=[Depends(require_token)])
async def patch_config(request: Request, body: dict):
    cfg = request.app.state.config
    restart_required = []

    for key, value in body.items():
        if key not in _IMMEDIATE_FIELDS and key not in _RESTART_FIELDS:
            raise HTTPException(422, {"error": f"unknown field: {key}"})
        expected_type = _VALID_TYPES[key]
        if not isinstance(value, expected_type):
            raise HTTPException(422, {"error": f"{key} must be {expected_type.__name__}"})
        if key in _BOUNDS:
            lo, hi = _BOUNDS[key]
            if lo is not None and value < lo:
                raise HTTPException(422, {"error": f"{key} must be >= {lo}"})
            if hi is not None and value > hi:
                raise HTTPException(422, {"error": f"{key} must be <= {hi}"})
        setattr(cfg, key, value)
        if key in _RESTART_FIELDS:
            restart_required.append(key)

    try:
        cfg.save()
    except Exception:
        pass  # best-effort save

    return {"restart_required": bool(restart_required), "changed": list(body.keys())}
