import os
import logging
from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import FileResponse

from config import config


logger = logging.getLogger("app")

router = APIRouter(prefix="/api", tags=["downloads"])


@router.get(
    "/download-document/{filename}",
    summary="下载生成的文档",
    description="根据文件名下载已生成的 .docx 文档。",
    responses={
        200: {"description": "下载成功（返回文件流）"},
        404: {"description": "文件不存在"},
    },
)
async def download_document(
    filename: str = Path(..., description="文件名（含扩展名），通常为 .docx")
):
    logger.debug(f"请求下载文件: {filename}")
    file_path = os.path.join(config.OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


