# 文档处理与生成API

这是一个基于FastAPI和OpenAI API开发的文档处理与生成服务，提供文档总结、目录结构生成和内容生成功能。所有处理任务都通过异步方式执行，提供任务状态查询和结果获取接口。

## 功能特点

1. **文档处理与总结**
   - 上传Word文档（.docx格式）
   - 智能分块处理文档内容
   - 并行处理文本块，提高效率
   - 生成精简总结（500字/块）
   - 最后生成综合总结（3000字内）

2. **目录结构生成**
   - 基于文档总结内容生成2-4层级的目录结构
   - 支持自定义最大目录层级
   - 返回JSON格式的目录数据
   - 逻辑清晰的章节层次关系

3. **文档内容生成**
   - 根据目录结构和总结内容，生成完整的文章内容
   - 并行处理一级目录，提高生成效率
   - 支持自定义Word文档模板
   - 生成可下载的Word文档

4. **异步任务处理**
   - 所有处理任务都以异步方式执行
   - 提供任务状态查询接口
   - 提供结果获取接口
   - 自动清理过期任务和结果

## 环境要求

- Python 3.8+
- 依赖包：见requirements.txt

## 安装与配置

1. 克隆代码库
2. 安装依赖：
   ```
   pip install -r requirements.txt
   ```
3. 配置环境变量（可通过.env文件或直接设置）：
   ```
   # OpenAI API配置
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_MODEL=gpt-3.5-turbo
   OPENAI_BASE_URL=https://api.openai.com/v1
   
   # 其他配置可选，有默认值
   ```

## 运行服务

```
python main.py
```

或使用uvicorn直接运行：

```
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## API接口说明

### 1. 处理文档并生成总结

- **URL**: `/api/process-document`
- **方法**: POST
- **参数**: 
  - `file`: Word文档文件（.docx格式）
- **返回**:
  ```json
  {
    "success": true,
    "message": "文档处理任务已创建",
    "task_id": "uuid-string"
  }
  ```

### 2. 生成目录结构

- **URL**: `/api/generate-outline`
- **方法**: POST
- **参数**: 
  - `summary`: 文档总结内容
  - `max_level`: 最大目录层级（2-4），默认为5
- **返回**:
  ```json
  {
    "success": true,
    "message": "目录生成任务已创建",
    "task_id": "uuid-string"
  }
  ```

### 3. 生成完整文档

- **URL**: `/api/generate-document`
- **方法**: POST
- **Content-Type**: multipart/form-data
- **参数**: 
  - `summary` (必填): 文档总结内容（至少10个字符）
  - `outline_json` (必填): 目录结构（JSON字符串）
  - `style_template` (可选): 样式模板，`A`/`B`/`C`/`D`/`E`，默认 `A`
  - `checklist_file` (可选): 清单文件，支持 `.pdf` `.docx` `.doc` `.xlsx` `.xls`
- **说明**:
  - `outline_json` 必须是有效的 JSON；参数校验失败将返回 400
  - 若提供 `checklist_file`，其解析出的文本会与 `summary` 合并用于生成（仅作参考整合，不会原样拷贝）
- **返回**:
  ```json
  {
    "success": true,
    "message": "文档生成任务已创建",
    "task_id": "uuid-string"
  }
  ```

### 4. 查询任务状态

- **URL**: `/api/task/{task_id}`
- **方法**: GET
- **参数**: 
  - `task_id`: 任务ID
- **返回**:
  ```json
  {
    "success": true,
    "task_id": "uuid-string",
    "status": "processing",
    "progress": 45,
    "message": "正在处理第3章节",
    "is_completed": false
  }
  ```

### 5. 获取任务结果

- **URL**: `/api/task/{task_id}/result`
- **方法**: GET
- **参数**: 
  - `task_id`: 任务ID
- **返回**: 根据任务类型返回相应的结果数据

### 6. 下载生成的文档

- **URL**: `/api/download-document/{filename}`
- **方法**: GET
- **参数**: 
  - `filename`: 文件名
- **返回**: Word文档文件

## 项目结构

```
.
├── main.py                  # 主应用程序入口
├── config.py                # 配置管理
├── document_processor.py    # 文档处理模块
├── outline_generator.py     # 目录生成模块
├── content_generator.py     # 内容生成模块
├── requirements.txt         # 依赖包列表
├── uploads/                 # 上传文件存储目录
└── output/                  # 生成文档输出目录
```

## 配置项说明

可通过环境变量或.env文件设置以下配置：

- `OPENAI_API_KEY`: OpenAI API密钥
- `OPENAI_MODEL`: 使用的模型，默认为"gpt-3.5-turbo"
- `OPENAI_BASE_URL`: API基础URL
- `MAX_CHUNK_SIZE`: 文本块最大大小，默认2000
- `CHUNK_OVERLAP`: 文本块重叠大小，默认200
- `SUMMARY_MAX_TOKENS`: 单个总结最大令牌数，默认500
- `FINAL_SUMMARY_MAX_TOKENS`: 最终总结最大令牌数，默认3000
- `MAX_CONCURRENT_REQUESTS`: 最大并发请求数，默认5
- `TASK_TIMEOUT`: 任务超时时间(秒)，默认3600
- `TASK_RESULT_TTL`: 任务结果保存时间(秒)，默认86400
- `HOST`: 服务主机，默认"0.0.0.0"
- `PORT`: 服务端口，默认8000
- `DEBUG`: 调试模式，默认True
- `UPLOAD_DIR`: 上传目录，默认"./uploads"
- `OUTPUT_DIR`: 输出目录，默认"./output" 