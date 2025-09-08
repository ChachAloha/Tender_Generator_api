from fastapi import APIRouter


router = APIRouter()


@router.get("/")
async def root():
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
            {"path": "/api/download-document/{filename}", "method": "GET", "description": "下载生成的文档"},
            {"path": "/api/model-configs", "method": "GET", "description": "列出模型配置（密钥脱敏）"},
            {"path": "/api/model-configs", "method": "POST", "description": "新增模型配置（可激活）"},
            {"path": "/api/model-configs/{id}", "method": "PATCH", "description": "更新模型配置（密钥可选）"},
            {"path": "/api/model-configs/{id}/activate", "method": "POST", "description": "切换激活配置"},
            {"path": "/api/model-configs/{id}", "method": "DELETE", "description": "删除模型配置"},
        ],
    }


