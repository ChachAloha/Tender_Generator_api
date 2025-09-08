import logging
from fastapi import APIRouter, HTTPException, Path

from services.tasks import task_manager, TaskStatus


logger = logging.getLogger("app")

router = APIRouter(prefix="/api", tags=["tasks"])


@router.get(
    "/task/{task_id}",
    summary="查询任务状态",
    description="根据任务 ID 返回当前状态与进度信息。",
    responses={
        200: {
            "description": "查询成功",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "task_id": "ab12cd34",
                        "status": "RUNNING",
                        "progress": 45,
                        "message": "处理中",
                        "is_completed": False,
                    }
                }
            },
        },
        404: {"description": "任务不存在"},
    },
)
async def get_task_status(task_id: str = Path(..., description="任务 ID", min_length=6, max_length=64)):
    logger.debug(f"查询任务状态: {task_id}")
    task_manager.cleanup()
    task_status = task_manager.get_task_status(task_id)
    if not task_status:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "success": True,
        "task_id": task_id,
        "status": task_status["status"],
        "progress": task_status["progress"],
        "message": task_status["message"],
        "is_completed": task_status["status"] == TaskStatus.COMPLETED,
    }


@router.get(
    "/task/{task_id}/result",
    summary="获取任务结果",
    description="当任务状态为已完成时，返回任务处理结果；否则返回 400。",
    responses={
        200: {"description": "获取成功"},
        400: {"description": "任务未完成"},
        404: {"description": "任务不存在或结果已过期"},
    },
)
async def get_task_result(task_id: str = Path(..., description="任务 ID", min_length=6, max_length=64)):
    logger.debug(f"获取任务结果: {task_id}")
    task_status = task_manager.get_task_status(task_id)
    if not task_status:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task_status["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"任务尚未完成，当前状态：{task_status['status']}")

    result = task_manager.get_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务结果不存在或已过期")

    return result


