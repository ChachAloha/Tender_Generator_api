from typing import Optional
import logging
from fastapi import APIRouter, HTTPException, Request, Path
from pydantic import BaseModel, Field

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
    name: str = Field(..., description="配置名称，便于区分用途")
    base_url: str = Field(..., description="模型服务的 Base URL")
    model: str = Field(..., description="模型名称或标识")
    api_key: str = Field(..., description="访问模型服务的 API Key")
    is_active: Optional[bool] = Field(False, description="是否设为激活配置，默认 false")


class ModelConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, description="配置名称")
    base_url: Optional[str] = Field(None, description="模型服务 Base URL")
    model: Optional[str] = Field(None, description="模型名称或标识")
    api_key: Optional[str] = Field(None, description="API Key")


@router.get(
    "/model-configs",
    summary="列出模型配置（密钥脱敏）",
    description="返回所有已保存的模型配置列表，密钥字段已脱敏。",
)
async def api_list_model_configs(request: Request):
    db_path = request.app.state.model_config_db_path
    items = list_model_configs(db_path)
    return {"success": True, "items": items}


@router.post(
    "/model-configs",
    summary="新增模型配置",
    description="创建新的模型配置，支持可选设为激活。",
    responses={
        200: {"description": "创建成功"},
        422: {"description": "参数校验失败"},
    },
)
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


@router.patch(
    "/model-configs/{config_id}",
    summary="更新模型配置",
    description="根据配置 ID 局部更新模型配置，未提供的字段保持不变。",
    responses={
        200: {"description": "更新成功"},
        404: {"description": "配置不存在"},
    },
)
async def api_update_model_config(request: Request, config_id: str = Path(..., description="配置 ID"), payload: ModelConfigUpdate = ...):
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


@router.post(
    "/model-configs/{config_id}/activate",
    summary="切换激活配置",
    description="将指定配置设置为当前激活配置。",
    responses={
        200: {"description": "切换成功"},
        404: {"description": "配置不存在"},
    },
)
async def api_activate_model_config(request: Request, config_id: str = Path(..., description="配置 ID")):
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


@router.delete(
    "/model-configs/{config_id}",
    summary="删除模型配置",
    description="根据配置 ID 删除模型配置。",
    responses={
        200: {"description": "删除成功"},
        404: {"description": "配置不存在或已删除"},
    },
)
async def api_delete_model_config(request: Request, config_id: str = Path(..., description="配置 ID")):
    db_path = request.app.state.model_config_db_path
    ok = delete_model_config(db_path, config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="配置不存在或已删除")
    return {"success": True}


