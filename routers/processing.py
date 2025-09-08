import json
import logging
from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, HTTPException, Request

from fastapi.responses import JSONResponse
from markitdown import MarkItDown

from config import config
from services.tasks import (
    save_upload_file,
    task_manager,
    generate_outline_task,
    generate_document_task,
    generate_supplementary_document_task,
)


logger = logging.getLogger("app")

router = APIRouter(prefix="/api", tags=["processing"])


@router.post("/process-document")
async def process_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    return_original: bool = Form(True, description="如果为true，则直接返回文档原文，跳过总结"),
):
    try:
        logger.info(f"收到文档处理请求: {file.filename}, return_original={return_original}")
        task_manager.cleanup()

        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        allowed_exts = (".pdf", ".docx")
        if not file.filename.lower().endswith(allowed_exts):
            raise HTTPException(status_code=400, detail="仅支持.pdf或.docx格式的文档")

        file_path = await save_upload_file(file)

        task_id = task_manager.create_task()

        db_path = request.app.state.model_config_db_path
        from services.tasks import process_document_task
        background_tasks.add_task(process_document_task, task_id, file_path, return_original, db_path)

        return {"success": True, "message": "文档处理任务已创建", "task_id": task_id}

    except Exception as e:
        logger.exception(f"处理文档请求失败: {file.filename}")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/generate-outline")
async def generate_outline(
    request: Request,
    background_tasks: BackgroundTasks,
    summary: str = Form(...),
    max_level: int = Form(4),
):
    try:
        logger.info(f"收到目录生成请求, max_level={max_level}")
        task_manager.cleanup()

        if not summary or len(summary.strip()) < 10:
            raise HTTPException(status_code=400, detail="总结内容过短或为空")

        if max_level < 1 or max_level > 4:
            raise HTTPException(status_code=400, detail="目录层级必须在1-4之间")

        task_id = task_manager.create_task()

        db_path = request.app.state.model_config_db_path
        background_tasks.add_task(generate_outline_task, task_id, summary, max_level, db_path)

        return {"success": True, "message": "目录生成任务已创建", "task_id": task_id}

    except Exception as e:
        logger.exception("生成目录请求失败")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/generate-document")
async def generate_document(
    request: Request,
    background_tasks: BackgroundTasks,
    summary: str = Form(...),
    outline_json: str = Form(...),
    style_template: str = Form("A"),
    checklist_file: UploadFile = File(None),
):
    try:
        logger.info(f"收到文档生成请求, style_template={style_template}")
        task_manager.cleanup()

        if not summary or len(summary.strip()) < 10:
            raise HTTPException(status_code=400, detail="总结内容过短或为空")

        if not outline_json:
            raise HTTPException(status_code=400, detail="缺少目录结构")

        if style_template not in ["A", "B", "C", "D", "E"]:
            raise HTTPException(status_code=400, detail="样式模板无效，请从A, B, C, D, E中选择")

        try:
            outline_data = json.loads(outline_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="目录结构JSON格式无效")

        merged_summary = summary
        if checklist_file and checklist_file.filename:
            allowed_exts = (".pdf", ".docx", ".doc", ".xlsx", ".xls")
            if not checklist_file.filename.lower().endswith(allowed_exts):
                raise HTTPException(status_code=400, detail="清单文件格式不支持，仅支持.pdf .docx .xlsx .xls")
            try:
                from services.tasks import save_upload_file as save_file

                checklist_path = await save_file(checklist_file)
                md = MarkItDown(enable_plugins=False)
                result_md = md.convert(checklist_path)
                checklist_markdown = (result_md.text_content or "").strip()
                if checklist_markdown:
                    merged_summary = (
                        f"{summary}\n\n完整清单文件内容(请根据当前章节标题和章节级别，选择性结合清单内容，进行整合，不需要完全照搬清单内容)：\n{checklist_markdown}"
                    )
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"清单文件解析失败: {str(e)}")

        task_id = task_manager.create_task()

        db_path = request.app.state.model_config_db_path
        background_tasks.add_task(
            generate_document_task, task_id, merged_summary, outline_data, style_template, db_path
        )

        return {"success": True, "message": "文档生成任务已创建", "task_id": task_id}

    except Exception as e:
        logger.exception("生成文档请求失败")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@router.post("/generate-supplementary-document")
async def generate_supplementary_document(
    request: Request,
    background_tasks: BackgroundTasks,
    summary: str = Form(...),
    user_request: str = Form(...),
    style_template: str = Form("A"),
):
    try:
        logger.info(f"收到补充文档生成请求, style_template={style_template}")
        task_manager.cleanup()

        if not summary or len(summary.strip()) < 10:
            raise HTTPException(status_code=400, detail="总结内容过短或为空")

        if not user_request or len(user_request.strip()) < 5:
            raise HTTPException(status_code=400, detail="用户补充需求过短或为空")

        if style_template not in ["A", "B", "C", "D", "E"]:
            raise HTTPException(status_code=400, detail="样式模板无效，请从A, B, C, D, E中选择")

        task_id = task_manager.create_task()

        db_path = request.app.state.model_config_db_path
        background_tasks.add_task(
            generate_supplementary_document_task, task_id, summary, user_request, style_template, db_path
        )

        return {"success": True, "message": "补充文档生成任务已创建", "task_id": task_id}

    except Exception as e:
        logger.exception("生成补充文档请求失败")
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


