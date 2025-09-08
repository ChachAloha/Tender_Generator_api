from typing import Optional
import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from model_config_store import (
    list_model_configs,
    create_model_config,
    update_model_config,
    activate_model_config,
    delete_model_config,
    get_model_config,
)


logger = logging.getLogger("app")

router = APIRouter(prefix="/api", tags=["model-configs"])


class ModelConfigCreate(BaseModel):
    name: str
    base_url: str
    model: str
    api_key: str
    is_active: Optional[bool] = False


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None


@router.get("/model-configs")
async def api_list_model_configs(request: Request):
    db_path = request.app.state.model_config_db_path
    items = list_model_configs(db_path)
    return {"success": True, "items": items}


@router.post("/model-configs")
async def api_create_model_config(request: Request, payload: ModelConfigCreate):
    db_path = request.app.state.model_config_db_path
    created = create_model_config(
        db_path=db_path,
        name=payload.name.strip(),
        base_url=payload.base_url.strip(),
        model=payload.model.strip(),
        api_key=payload.api_key.strip(),
        is_active=bool(payload.is_active),
    )
    return {
        "success": True,
        "item": {
            "id": created["id"],
            "name": created["name"],
            "base_url": created["base_url"],
            "model": created["model"],
            "api_key_masked": "***",
            "is_active": created["is_active"],
        },
    }


@router.patch("/model-configs/{config_id}")
async def api_update_model_config(request: Request, config_id: str, payload: ModelConfigUpdate):
    db_path = request.app.state.model_config_db_path
    existing = get_model_config(db_path, config_id)
    if not existing:
        raise HTTPException(status_code=404, detail="配置不存在")
    updated = update_model_config(
        db_path=db_path,
        config_id=config_id,
        name=payload.name.strip() if payload.name is not None else None,
        base_url=payload.base_url.strip() if payload.base_url is not None else None,
        model=payload.model.strip() if payload.model is not None else None,
        api_key=payload.api_key.strip() if payload.api_key is not None else None,
    )
    assert updated is not None
    return {
        "success": True,
        "item": {
            "id": updated["id"],
            "name": updated["name"],
            "base_url": updated["base_url"],
            "model": updated["model"],
            "api_key_masked": "***",
            "is_active": bool(updated["is_active"]),
        },
    }


@router.post("/model-configs/{config_id}/activate")
async def api_activate_model_config(request: Request, config_id: str):
    db_path = request.app.state.model_config_db_path
    ok = activate_model_config(db_path, config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="配置不存在")
    item = get_model_config(db_path, config_id)
    return {
        "success": True,
        "item": {
            "id": item["id"],
            "name": item["name"],
            "base_url": item["base_url"],
            "model": item["model"],
            "api_key_masked": "***",
            "is_active": True,
        },
    }


@router.delete("/model-configs/{config_id}")
async def api_delete_model_config(request: Request, config_id: str):
    db_path = request.app.state.model_config_db_path
    ok = delete_model_config(db_path, config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="配置不存在或已删除")
    return {"success": True}


