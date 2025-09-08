import os
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from config import config


logger = logging.getLogger("app")

router = APIRouter(prefix="/api", tags=["downloads"])


@router.get("/download-document/{filename}")
async def download_document(filename: str):
    logger.debug(f"请求下载文件: {filename}")
    file_path = os.path.join(config.OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


