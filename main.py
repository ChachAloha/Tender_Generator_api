import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from config import config, validate_config
from logging_config import setup_logging
from model_config_store import init_db, get_active_model_config
from routers.processing import router as processing_router
from routers.tasks import router as tasks_router
from routers.downloads import router as downloads_router
from routers.model_configs import router as model_configs_router
from routers.root import router as root_router

# 配置日志
setup_logging()
logger = logging.getLogger("app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    validate_config()
    # 初始化SQLite
    db_path = os.path.join(os.getcwd(), "data", "model_configs.db")
    init_db(db_path)
    # 记录是否存在激活配置
    active_cfg = get_active_model_config(db_path)
    if active_cfg is None:
        logger.warning("未在数据库中找到激活的模型配置，将回退使用环境变量中的OPENAI配置。")
    app.state.model_config_db_path = db_path
    logger.info("应用启动完成")
    yield
    # 关闭时执行
    logger.info("应用正在关闭")

openapi_tags = [
    {
        "name": "processing",
        "description": "文档处理相关接口：上传文档、生成目录、生成文档与补充文档（异步任务）。",
    },
    {
        "name": "tasks",
        "description": "任务查询接口：根据任务 ID 查询状态与结果。",
    },
    {
        "name": "downloads",
        "description": "下载接口：下载已生成的文档文件。",
    },
    {
        "name": "model-configs",
        "description": "模型配置接口：创建、更新、激活与删除模型配置。",
    },
]

app = FastAPI(
    title="文档处理与生成API",
    description="提供文档总结、目录生成和内容生成功能的API服务",
    version="1.3.0",
    lifespan=lifespan,
    openapi_tags=openapi_tags,
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由分组
app.include_router(processing_router)
app.include_router(tasks_router)
app.include_router(downloads_router)
app.include_router(model_configs_router)
app.include_router(root_router)

"""
路由与任务逻辑已拆分到 routers/ 与 services/ 目录。
"""

# 注意：启动配置已移至 lifespan 事件处理器

if __name__ == "__main__":
    # 启动应用
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )
