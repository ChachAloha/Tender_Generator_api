import os
import uuid
import time
import logging
import asyncio
from typing import Dict, Optional, Any

from fastapi import HTTPException, UploadFile

from config import config
from document_processor import DocumentProcessor
from outline_generator import OutlineGenerator
from content_generator import ContentGenerator
from model_config_store import get_active_model_config


logger = logging.getLogger("app")


class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
        self.last_cleanup = time.time()

    def create_task(self) -> str:
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            "status": TaskStatus.PENDING,
            "progress": 0,
            "message": "任务已创建",
            "created_at": time.time(),
        }
        logger.info(f"创建新任务，ID: {task_id}")
        return task_id

    def update_task(
        self,
        task_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
    ) -> bool:
        if task_id in self.tasks:
            if status:
                self.tasks[task_id]["status"] = status
            if progress is not None:
                self.tasks[task_id]["progress"] = progress
            if message:
                self.tasks[task_id]["message"] = message
            logger.debug(
                f"更新任务状态: ID={task_id}, Status={status}, Progress={progress}, Message={message}"
            )
            return True
        return False

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.tasks.get(task_id)

    def save_result(self, task_id: str, result: Any) -> bool:
        if task_id in self.tasks:
            self.results[task_id] = {"data": result, "created_at": time.time()}
            return True
        return False

    def get_result(self, task_id: str) -> Optional[Any]:
        if task_id in self.results:
            return self.results[task_id]["data"]
        return None

    def _cleanup_directory(self, directory: str, ttl_seconds: int) -> int:
        """删除目录中超过TTL的文件，返回删除数量。"""
        removed = 0
        now = time.time()
        try:
            os.makedirs(directory, exist_ok=True)
            for name in os.listdir(directory):
                path = os.path.join(directory, name)
                try:
                    if os.path.isfile(path):
                        mtime = os.path.getmtime(path)
                        if now - mtime > ttl_seconds:
                            os.remove(path)
                            removed += 1
                    elif os.path.isdir(path):
                        # 可选：清理空目录
                        if not os.listdir(path):
                            # 跳过：仅当需要时删除空目录
                            pass
                except Exception as e:
                    logger.warning(f"清理文件失败: {path} - {e}")
        except Exception as e:
            logger.warning(f"遍历目录失败: {directory} - {e}")
        return removed

    def cleanup(self) -> int:
        current_time = time.time()
        if current_time - self.last_cleanup < 3600:
            return 0

        count = 0

        # 清理超时任务
        expired_tasks = [
            task_id
            for task_id, task in self.tasks.items()
            if (
                current_time - task["created_at"] > config.TASK_TIMEOUT
                and task["status"] in [TaskStatus.PENDING, TaskStatus.PROCESSING]
            )
        ]

        for task_id in expired_tasks:
            self.tasks[task_id]["status"] = TaskStatus.FAILED
            self.tasks[task_id]["message"] = "任务超时"
            count += 1

        # 清理过期结果
        expired_results = [
            task_id
            for task_id, result in self.results.items()
            if current_time - result["created_at"] > config.TASK_RESULT_TTL
        ]

        for task_id in expired_results:
            del self.results[task_id]
            count += 1

        # 文件系统清理（uploads/output）
        count += self._cleanup_directory(config.UPLOAD_DIR, config.UPLOAD_TTL)
        count += self._cleanup_directory(config.OUTPUT_DIR, config.OUTPUT_TTL)

        self.last_cleanup = current_time
        return count


# 单例任务管理器和会话缓存
task_manager = TaskManager()
summary_cache: Dict[str, str] = {}


async def save_upload_file(upload_file: UploadFile) -> str:
    if not upload_file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    file_extension = os.path.splitext(upload_file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(config.UPLOAD_DIR, unique_filename)

    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(await upload_file.read())
    return file_path


async def process_document_task(
    task_id: str,
    file_path: str,
    return_original: bool = True,
    db_path: Optional[str] = None,
):
    try:
        logger.info(
            f"任务 {task_id}: 开始处理文档 {file_path}, return_original={return_original}"
        )
        task_manager.update_task(task_id, TaskStatus.PROCESSING, 10, "开始处理文档")

        if return_original:
            task_manager.update_task(task_id, progress=30, message="正在提取原文")
            try:
                def convert_with_markitdown(path: str) -> str:
                    from markitdown import MarkItDown  # type: ignore

                    md = MarkItDown(enable_plugins=False)
                    res = md.convert(path)
                    return (res.text_content or "").strip()

                original_markdown = await asyncio.to_thread(
                    convert_with_markitdown, file_path
                )
            except Exception as e:
                logger.error(f"任务 {task_id}: 提取原文失败 - {str(e)}")
                task_manager.update_task(
                    task_id, TaskStatus.FAILED, 100, f"提取原文失败: {str(e)}"
                )
                return

            task_manager.update_task(task_id, progress=80, message="原文提取完成")
            session_id = str(uuid.uuid4())
            summary_cache[session_id] = original_markdown
            task_result = {
                "success": True,
                "session_id": session_id,
                "original_length": len(original_markdown),
                "chunks_count": 0,
                "final_summary": original_markdown,
                "processing_info": {"summary_skipped": True, "format": "markdown"},
            }
            task_manager.save_result(task_id, task_result)
            task_manager.update_task(task_id, TaskStatus.COMPLETED, 100, "原文提取完成")
            logger.info(f"任务 {task_id}: 原文提取成功")
            return

        if not db_path:
            raise RuntimeError("缺少数据库路径用于读取激活配置")

        active_cfg = get_active_model_config(db_path)
        processor = DocumentProcessor(active_cfg)
        result = await processor.process_document(file_path)

        if not result["success"]:
            logger.error(f"任务 {task_id}: 文档处理失败 - {result['error']}")
            task_manager.update_task(task_id, TaskStatus.FAILED, 100, result["error"])
            return

        session_id = str(uuid.uuid4())
        summary_cache[session_id] = result["final_summary"]

        task_result = {
            "success": True,
            "session_id": session_id,
            "original_length": result["original_text_length"],
            "chunks_count": result["chunks_count"],
            "final_summary": result["final_summary"],
            "processing_info": result["processing_info"],
        }

        task_manager.save_result(task_id, task_result)
        task_manager.update_task(task_id, TaskStatus.COMPLETED, 100, "文档处理完成")
        logger.info(f"任务 {task_id}: 文档处理成功")

    except Exception as e:
        logger.exception(f"任务 {task_id}: 处理文档时发生未捕获的异常")
        task_manager.update_task(task_id, TaskStatus.FAILED, 100, f"处理失败: {str(e)}")
    finally:
        # 删除上传的临时文件（若存在）
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"删除上传临时文件失败: {file_path} - {e}")


async def generate_outline_task(
    task_id: str, summary_content: str, max_level: int = 4, db_path: Optional[str] = None
):
    try:
        logger.info(f"任务 {task_id}: 开始生成目录, max_level={max_level}")
        task_manager.update_task(task_id, TaskStatus.PROCESSING, 10, "开始生成目录")

        if not db_path:
            raise RuntimeError("缺少数据库路径用于读取激活配置")

        active_cfg = get_active_model_config(db_path)
        og = OutlineGenerator(active_cfg)
        result = await og.generate_outline(summary_content, max_level)

        if not result["success"]:
            logger.error(f"任务 {task_id}: 目录生成失败 - {result['error']}")
            task_manager.update_task(task_id, TaskStatus.FAILED, 100, result["error"])
            return

        task_manager.save_result(
            task_id,
            {"success": True, "outline": result["outline"], "total_sections": result["total_sections"]},
        )

        task_manager.update_task(task_id, TaskStatus.COMPLETED, 100, "目录生成完成")
        logger.info(f"任务 {task_id}: 目录生成成功")

    except Exception as e:
        logger.exception(f"任务 {task_id}: 生成目录时发生未捕获的异常")
        task_manager.update_task(task_id, TaskStatus.FAILED, 100, f"生成失败: {str(e)}")


async def generate_document_task(
    task_id: str,
    summary: str,
    outline_data: Dict[str, Any],
    style_template: str = "A",
    enable_continuation: bool = False,
    db_path: Optional[str] = None,
):
    try:
        logger.info(f"任务 {task_id}: 开始生成文档, style_template={style_template}, enable_continuation={enable_continuation}")
        task_manager.update_task(task_id, TaskStatus.PROCESSING, 10, "开始生成文档内容")

        if not db_path:
            raise RuntimeError("缺少数据库路径用于读取激活配置")

        active_cfg = get_active_model_config(db_path)
        cg = ContentGenerator(active_cfg)
        result = await cg.generate_document(summary, outline_data, style_template, enable_continuation)

        if not result["success"]:
            logger.error(f"任务 {task_id}: 文档生成失败 - {result['error']}")
            task_manager.update_task(task_id, TaskStatus.FAILED, 100, result["error"])
            return

        doc_filename = os.path.basename(result["document_path"])
        download_link = f"/api/download-document/{doc_filename}"

        task_result = {
            "success": True,
            "document_path": result["document_path"],
            "sections_count": result["sections_count"],
            "download_link": download_link,
        }

        task_manager.save_result(task_id, task_result)
        task_manager.update_task(task_id, TaskStatus.COMPLETED, 100, "文档生成完成")
        logger.info(f"任务 {task_id}: 文档生成成功")

    except Exception as e:
        logger.exception(f"任务 {task_id}: 生成文档时发生未捕获的异常")
        task_manager.update_task(task_id, TaskStatus.FAILED, 100, f"生成失败: {str(e)}")


async def generate_supplementary_document_task(
    task_id: str,
    user_request: str,
    style_template: str = "A",
    db_path: Optional[str] = None,
):
    try:
        logger.info(f"任务 {task_id}: 开始生成补充文档, style_template={style_template}")
        task_manager.update_task(task_id, TaskStatus.PROCESSING, 10, "开始生成补充文档")

        if not db_path:
            raise RuntimeError("缺少数据库路径用于读取激活配置")

        active_cfg = get_active_model_config(db_path)
        cg = ContentGenerator(active_cfg)
        result = await cg.generate_supplementary_document(user_request, style_template)

        if not result["success"]:
            error_message = result.get("error", "未知错误")
            logger.error(f"任务 {task_id}: 补充文档生成失败 - {error_message}")
            task_manager.update_task(task_id, TaskStatus.FAILED, 100, error_message)
            return

        doc_filename = os.path.basename(result["document_path"])
        download_link = f"/api/download-document/{doc_filename}"

        task_result = {
            "success": True,
            "document_path": result["document_path"],
            "plain_text": result["plain_text"],
            "sections_count": result["sections_count"],
            "download_link": download_link,
        }

        task_manager.save_result(task_id, task_result)
        task_manager.update_task(task_id, TaskStatus.COMPLETED, 100, "补充文档生成完成")
        logger.info(f"任务 {task_id}: 补充文档生成成功")

    except Exception as e:
        logger.exception(f"任务 {task_id}: 生成补充文档时发生未捕获的异常")
        task_manager.update_task(task_id, TaskStatus.FAILED, 100, f"生成失败: {str(e)}")


