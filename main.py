import os
import uuid
import time
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import config, validate_config
from document_processor import DocumentProcessor
from outline_generator import OutlineGenerator
from content_generator import ContentGenerator
from logging_config import setup_logging

# 配置日志
setup_logging()
logger = logging.getLogger("app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    validate_config()
    logger.info("应用启动完成")
    yield
    # 关闭时执行
    logger.info("应用正在关闭")

app = FastAPI(
    title="文档处理与生成API",
    description="提供文档总结、目录生成和内容生成功能的API服务",
    version="1.2.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化处理器
document_processor = DocumentProcessor()
outline_generator = OutlineGenerator()
content_generator = ContentGenerator()

# 任务存储
class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.results = {}
        self.last_cleanup = time.time()
    
    def create_task(self) -> str:
        task_id = str(uuid.uuid4())
        self.tasks[task_id] = {
            "status": TaskStatus.PENDING,
            "progress": 0,
            "message": "任务已创建",
            "created_at": time.time()
        }
        logger.info(f"创建新任务，ID: {task_id}")
        return task_id
    
    def update_task(self, task_id: str, status: Optional[str] = None, progress: Optional[int] = None, message: Optional[str] = None) -> bool:
        if task_id in self.tasks:
            if status:
                self.tasks[task_id]["status"] = status
            if progress is not None:
                self.tasks[task_id]["progress"] = progress
            if message:
                self.tasks[task_id]["message"] = message
            logger.debug(f"更新任务状态: ID={task_id}, Status={status}, Progress={progress}, Message={message}")
            return True
        return False
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        return self.tasks.get(task_id)
    
    def save_result(self, task_id: str, result: Any) -> bool:
        if task_id in self.tasks:
            self.results[task_id] = {
                "data": result,
                "created_at": time.time()
            }
            return True
        return False
    
    def get_result(self, task_id: str) -> Optional[Any]:
        if task_id in self.results:
            return self.results[task_id]["data"]
        return None
    
    def cleanup(self) -> int:
        """清理过期的任务和结果"""
        current_time = time.time()
        
        # 仅在距离上次清理超过一小时时执行
        if current_time - self.last_cleanup < 3600:
            return 0
        
        count = 0
        
        # 清理任务状态
        expired_tasks = [
            task_id for task_id, task in self.tasks.items()
            if (current_time - task["created_at"] > config.TASK_TIMEOUT and
                task["status"] in [TaskStatus.PENDING, TaskStatus.PROCESSING])
        ]
        
        for task_id in expired_tasks:
            self.tasks[task_id]["status"] = TaskStatus.FAILED
            self.tasks[task_id]["message"] = "任务超时"
            count += 1
        
        # 清理结果
        expired_results = [
            task_id for task_id, result in self.results.items()
            if current_time - result["created_at"] > config.TASK_RESULT_TTL
        ]
        
        for task_id in expired_results:
            del self.results[task_id]
            count += 1
        
        self.last_cleanup = current_time
        return count

# 创建任务管理器
task_manager = TaskManager()

# 保存上传的文件
async def save_upload_file(upload_file: UploadFile) -> str:
    """保存上传的文件并返回保存路径"""
    # 创建唯一文件名
    if not upload_file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    file_extension = os.path.splitext(upload_file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(config.UPLOAD_DIR, unique_filename)
    
    # 确保目录存在
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    
    # 保存文件
    with open(file_path, "wb") as f:
        f.write(await upload_file.read())
    
    return file_path

# 会话存储
summary_cache = {}

async def process_document_task(task_id: str, file_path: str, return_original: bool = True):
    """文档处理后台任务"""
    try:
        logger.info(f"任务 {task_id}: 开始处理文档 {file_path}, return_original={return_original}")
        task_manager.update_task(task_id, TaskStatus.PROCESSING, 10, "开始处理文档")

        if return_original:
            task_manager.update_task(task_id, progress=30, message="正在提取原文")
            
            try:
                # 使用 to_thread 避免阻塞事件循环
                original_text = await asyncio.to_thread(document_processor.extract_text_from_docx, file_path)
            except Exception as e:
                logger.error(f"任务 {task_id}: 提取原文失败 - {str(e)}")
                task_manager.update_task(task_id, TaskStatus.FAILED, 100, f"提取原文失败: {str(e)}")
                return

            task_manager.update_task(task_id, progress=80, message="原文提取完成")
            
            session_id = str(uuid.uuid4())
            summary_cache[session_id] = original_text
            
            task_result = {
                "success": True,
                "session_id": session_id,
                "original_length": len(original_text),
                "chunks_count": 0,
                "final_summary": original_text,
                "processing_info": {"summary_skipped": True}
            }
            
            task_manager.save_result(task_id, task_result)
            task_manager.update_task(task_id, TaskStatus.COMPLETED, 100, "原文提取完成")
            logger.info(f"任务 {task_id}: 原文提取成功")
            return
        
        # 处理文档
        result = await document_processor.process_document(file_path)
        
        if not result["success"]:
            logger.error(f"任务 {task_id}: 文档处理失败 - {result['error']}")
            task_manager.update_task(task_id, TaskStatus.FAILED, 100, result["error"])
            return
        
        # 保存总结到缓存，用于后续API调用
        session_id = str(uuid.uuid4())
        summary_cache[session_id] = result["final_summary"]
        
        # 保存结果
        task_result = {
            "success": True,
            "session_id": session_id,
            "original_length": result["original_text_length"],
            "chunks_count": result["chunks_count"],
            "final_summary": result["final_summary"],
            "processing_info": result["processing_info"]
        }
        
        task_manager.save_result(task_id, task_result)
        task_manager.update_task(task_id, TaskStatus.COMPLETED, 100, "文档处理完成")
        logger.info(f"任务 {task_id}: 文档处理成功")
    
    except Exception as e:
        logger.exception(f"任务 {task_id}: 处理文档时发生未捕获的异常")
        task_manager.update_task(task_id, TaskStatus.FAILED, 100, f"处理失败: {str(e)}")
        
async def generate_outline_task(task_id: str, summary_content: str, max_level: int = 4):
    """目录生成后台任务"""
    try:
        logger.info(f"任务 {task_id}: 开始生成目录, max_level={max_level}")
        task_manager.update_task(task_id, TaskStatus.PROCESSING, 10, "开始生成目录")
        
        # 生成目录
        result = await outline_generator.generate_outline(summary_content, max_level)
        
        if not result["success"]:
            logger.error(f"任务 {task_id}: 目录生成失败 - {result['error']}")
            task_manager.update_task(task_id, TaskStatus.FAILED, 100, result["error"])
            return
        
        # 保存结果
        task_manager.save_result(task_id, {
            "success": True,
            "outline": result["outline"],
            "total_sections": result["total_sections"]
        })
        
        task_manager.update_task(task_id, TaskStatus.COMPLETED, 100, "目录生成完成")
        logger.info(f"任务 {task_id}: 目录生成成功")
    
    except Exception as e:
        logger.exception(f"任务 {task_id}: 生成目录时发生未捕获的异常")
        task_manager.update_task(task_id, TaskStatus.FAILED, 100, f"生成失败: {str(e)}")

async def generate_document_task(task_id: str, summary: str, outline_data: Dict, style_template: str = 'A'):
    """文档生成后台任务"""
    try:
        logger.info(f"任务 {task_id}: 开始生成文档, style_template={style_template}")
        task_manager.update_task(task_id, TaskStatus.PROCESSING, 10, "开始生成文档内容")
        
        # 生成文档
        result = await content_generator.generate_document(summary, outline_data, style_template)
        
        if not result["success"]:
            logger.error(f"任务 {task_id}: 文档生成失败 - {result['error']}")
            task_manager.update_task(task_id, TaskStatus.FAILED, 100, result["error"])
            return
        
        # 生成下载链接
        doc_filename = os.path.basename(result["document_path"])
        download_link = f"/api/download-document/{doc_filename}"
        
        # 保存结果
        task_result = {
            "success": True,
            "document_path": result["document_path"],
            "sections_count": result["sections_count"],
            "download_link": download_link
        }
        
        task_manager.save_result(task_id, task_result)
        task_manager.update_task(task_id, TaskStatus.COMPLETED, 100, "文档生成完成")
        logger.info(f"任务 {task_id}: 文档生成成功")
    
    except Exception as e:
        logger.exception(f"任务 {task_id}: 生成文档时发生未捕获的异常")
        task_manager.update_task(task_id, TaskStatus.FAILED, 100, f"生成失败: {str(e)}")

async def generate_supplementary_document_task(task_id: str, summary: str, user_request: str, style_template: str = 'A'):
    """补充文档生成后台任务"""
    try:
        logger.info(f"任务 {task_id}: 开始生成补充文档, style_template={style_template}")
        task_manager.update_task(task_id, TaskStatus.PROCESSING, 10, "开始生成补充文档")
        
        # 调用新的生成器方法
        result = await content_generator.generate_supplementary_document(summary, user_request, style_template)
        
        if not result["success"]:
            error_message = result.get('error', '未知错误')
            logger.error(f"任务 {task_id}: 补充文档生成失败 - {error_message}")
            task_manager.update_task(task_id, TaskStatus.FAILED, 100, error_message)
            return
        
        # 生成下载链接
        doc_filename = os.path.basename(result["document_path"])
        download_link = f"/api/download-document/{doc_filename}"
        
        # 保存结果
        task_result = {
            "success": True,
            "document_path": result["document_path"],
            "plain_text": result["plain_text"],
            "sections_count": result["sections_count"],
            "download_link": download_link
        }
        
        task_manager.save_result(task_id, task_result)
        task_manager.update_task(task_id, TaskStatus.COMPLETED, 100, "补充文档生成完成")
        logger.info(f"任务 {task_id}: 补充文档生成成功")
    
    except Exception as e:
        logger.exception(f"任务 {task_id}: 生成补充文档时发生未捕获的异常")
        task_manager.update_task(task_id, TaskStatus.FAILED, 100, f"生成失败: {str(e)}")

@app.post("/api/process-document")
async def process_document(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    return_original: bool = Form(True, description="如果为true，则直接返回文档原文，跳过总结")
):
    """
    上传Word文档，将其分块并生成总结（异步任务）
    
    - **file**: Word文档文件（.docx格式）
    - **return_original**: 如果为true，则直接返回文档原文，跳过总结
    
    返回：
    - **task_id**: 任务ID，用于查询进度
    """
    try:
        logger.info(f"收到文档处理请求: {file.filename}, return_original={return_original}")
        # 清理过期任务
        task_manager.cleanup()
        
        # 检查文件类型
        if not file.filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")
        if not file.filename.endswith(('.docx')):
            raise HTTPException(status_code=400, detail="只支持.docx格式的Word文档")
        
        # 保存文件
        file_path = await save_upload_file(file)
        
        # 创建任务
        task_id = task_manager.create_task()
        
        # 启动后台任务
        background_tasks.add_task(process_document_task, task_id, file_path, return_original)
        
        return {
            "success": True,
            "message": "文档处理任务已创建",
            "task_id": task_id
        }
    
    except Exception as e:
        logger.exception(f"处理文档请求失败: {file.filename}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/generate-outline")
async def generate_outline(
    background_tasks: BackgroundTasks,
    summary: str = Form(...), 
    max_level: int = Form(4)
):
    """
    根据总结内容生成目录结构（异步任务）
    
    - **summary**: 文档总结内容
    - **max_level**: 最大目录层级（1-4），默认为4
    
    返回：
    - **task_id**: 任务ID，用于查询进度
    """
    try:
        logger.info(f"收到目录生成请求, max_level={max_level}")
        # 清理过期任务
        task_manager.cleanup()
        
        # 验证参数
        if not summary or len(summary.strip()) < 10:
            raise HTTPException(status_code=400, detail="总结内容过短或为空")
        
        if max_level < 1 or max_level > 4:
            raise HTTPException(status_code=400, detail="目录层级必须在1-4之间")
        
        # 创建任务
        task_id = task_manager.create_task()
        
        # 启动后台任务
        background_tasks.add_task(generate_outline_task, task_id, summary, max_level)
        
        return {
            "success": True,
            "message": "目录生成任务已创建",
            "task_id": task_id
        }
    
    except Exception as e:
        logger.exception("生成目录请求失败")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/generate-document")
async def generate_document(
    background_tasks: BackgroundTasks,
    summary: str = Form(...),
    outline_json: str = Form(...),
    style_template: str = Form('A'),
    checklist_file: UploadFile = File(None)
):
    """
    根据总结内容和目录结构生成完整文档（异步任务）

    - Content-Type: multipart/form-data

    - 参数:
      - summary (必填): 文档总结内容（至少10个字符）
      - outline_json (必填): 目录结构（JSON字符串）
      - style_template (可选): 样式模板 (A, B, C, D, E)，默认为 A
      - checklist_file (可选): 清单文件，支持 .pdf .docx .doc .xlsx .xls

    - 说明:
      - outline_json 必须是有效的 JSON；参数校验失败将返回 400
      - 若提供 checklist_file，其解析出的文本会与 summary 合并用于生成（仅作参考整合，不会原样拷贝）

    返回：
    - task_id: 任务ID，用于查询进度
    """
    try:
        logger.info(f"收到文档生成请求, style_template={style_template}")
        # 清理过期任务
        task_manager.cleanup()
        
        # 验证参数
        if not summary or len(summary.strip()) < 10:
            raise HTTPException(status_code=400, detail="总结内容过短或为空")
        
        if not outline_json:
            raise HTTPException(status_code=400, detail="缺少目录结构")
        
        if style_template not in ['A', 'B', 'C', 'D', 'E']:
            raise HTTPException(status_code=400, detail="样式模板无效，请从A, B, C, D, E中选择")
        
        # 解析目录JSON
        import json
        try:
            outline_data = json.loads(outline_json)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="目录结构JSON格式无效")

        # 处理可选清单文件
        merged_summary = summary
        if checklist_file and checklist_file.filename:
            allowed_exts = ('.pdf', '.docx', '.doc', '.xlsx', '.xls')
            if not checklist_file.filename.lower().endswith(allowed_exts):
                raise HTTPException(status_code=400, detail="清单文件格式不支持，仅支持.pdf .docx .doc .xlsx .xls")
            try:
                checklist_path = await save_upload_file(checklist_file)
                # 使用文档处理器解析任意格式
                checklist_text = document_processor.extract_text_from_any(checklist_path)
                if checklist_text and checklist_text.strip():
                    merged_summary = f"{summary}\n\n清单文件内容（供参考整合，不直接照搬）：\n{checklist_text}"
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"清单文件解析失败: {str(e)}")
        
        # 创建任务
        task_id = task_manager.create_task()
        
        # 启动后台任务（将合并后的摘要传入生成流程）
        background_tasks.add_task(generate_document_task, task_id, merged_summary, outline_data, style_template)
        
        return {
            "success": True,
            "message": "文档生成任务已创建",
            "task_id": task_id
        }
    
    except Exception as e:
        logger.exception("生成文档请求失败")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/generate-supplementary-document")
async def generate_supplementary_document(
    background_tasks: BackgroundTasks,
    summary: str = Form(...),
    user_request: str = Form(...),
    style_template: str = Form('A')
):
    """
    根据总结、用户需求和样式模板生成补充文档（异步任务）
    
    - **summary**: 文档总结内容
    - **user_request**: 用户的具体补充需求
    - **style_template**: 样式模板 (A, B, C, D, E)，默认为A
    
    返回：
    - **task_id**: 任务ID，用于查询进度
    """
    try:
        logger.info(f"收到补充文档生成请求, style_template={style_template}")
        task_manager.cleanup()
        
        # 验证参数
        if not summary or len(summary.strip()) < 10:
            raise HTTPException(status_code=400, detail="总结内容过短或为空")
        
        if not user_request or len(user_request.strip()) < 5:
            raise HTTPException(status_code=400, detail="用户补充需求过短或为空")
        
        if style_template not in ['A', 'B', 'C', 'D', 'E']:
            raise HTTPException(status_code=400, detail="样式模板无效，请从A, B, C, D, E中选择")
        
        # 创建任务
        task_id = task_manager.create_task()
        
        # 启动后台任务
        background_tasks.add_task(generate_supplementary_document_task, task_id, summary, user_request, style_template)
        
        return {
            "success": True,
            "message": "补充文档生成任务已创建",
            "task_id": task_id
        }
    
    except Exception as e:
        logger.exception("生成补充文档请求失败")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/task/{task_id}")
async def get_task_status(task_id: str):
    """
    查询任务状态
    
    - **task_id**: 任务ID
    
    返回：
    - **status**: 任务状态 (pending, processing, completed, failed)
    - **progress**: 进度百分比
    - **message**: 状态消息
    """
    logger.debug(f"查询任务状态: {task_id}")
    # 清理过期任务
    task_manager.cleanup()
    
    # 获取任务状态
    task_status = task_manager.get_task_status(task_id)
    if not task_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return {
        "success": True,
        "task_id": task_id,
        "status": task_status["status"],
        "progress": task_status["progress"],
        "message": task_status["message"],
        "is_completed": task_status["status"] == TaskStatus.COMPLETED
    }

@app.get("/api/task/{task_id}/result")
async def get_task_result(task_id: str):
    """
    获取任务结果
    
    - **task_id**: 任务ID
    
    返回：
    - 任务完成的结果数据
    """
    logger.debug(f"获取任务结果: {task_id}")
    # 获取任务状态
    task_status = task_manager.get_task_status(task_id)
    if not task_status:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    # 检查任务是否完成
    if task_status["status"] != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"任务尚未完成，当前状态：{task_status['status']}")
    
    # 获取结果
    result = task_manager.get_result(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="任务结果不存在或已过期")
    
    return result

@app.get("/api/download-document/{filename}")
async def download_document(filename: str):
    """
    下载生成的文档
    
    - **filename**: 文件名
    """
    logger.debug(f"请求下载文件: {filename}")
    file_path = os.path.join(config.OUTPUT_DIR, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

@app.get("/")
async def root():
    """API根路径，返回服务信息"""
    return {
        "service": "文档处理与生成API",
        "version": "1.1.0",
        "status": "运行中",
        "endpoints": [
            {"path": "/api/process-document", "method": "POST", "description": "处理并总结文档（异步）"},
            {"path": "/api/generate-outline", "method": "POST", "description": "根据总结生成目录结构（异步）"},
            {"path": "/api/generate-document", "method": "POST", "description": "根据总结和目录生成文档（异步）"},
            {"path": "/api/generate-supplementary-document", "method": "POST", "description": "生成补充说明文档（异步）"},
            {"path": "/api/task/{task_id}", "method": "GET", "description": "查询任务状态"},
            {"path": "/api/task/{task_id}/result", "method": "GET", "description": "获取任务结果"},
            {"path": "/api/download-document/{filename}", "method": "GET", "description": "下载生成的文档"}
        ]
    }

# 注意：启动配置已移至 lifespan 事件处理器

if __name__ == "__main__":
    # 启动应用
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )
