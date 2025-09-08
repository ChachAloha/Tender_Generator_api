import logging
from fastapi import APIRouter, HTTPException

from services.tasks import task_manager, TaskStatus


logger = logging.getLogger("app")

router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
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


@router.get("/task/{task_id}/result")
async def get_task_result(task_id: str):
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


