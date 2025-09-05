### /api/generate-document 接口说明

- **用途**: 根据总结与目录结构生成完整文档（异步任务）
- **方法**: POST
- **路径**: `/api/generate-document`
- **Content-Type**: `multipart/form-data`
- **鉴权**: 无

### 请求参数

- **summary** (必填, string): 文档总结内容，至少 10 个字符
- **outline_json** (必填, string): 目录结构的 JSON 字符串（建议直接使用 `/api/generate-outline` 的输出）
- **style_template** (可选, string): 样式模板，枚举值 `A | B | C | D | E`，默认 `A`
- **checklist_file** (可选, file): 清单文件，支持 `.pdf .docx .doc .xlsx .xls`
  - 清单内容将与 `summary` 合并作为参考进行生成，不会原样拷贝

### 成功响应

- **状态码**: 200
- **响应体**:
```json
{
  "success": true,
  "message": "文档生成任务已创建",
  "task_id": "c8f0a0e1-7b0a-4a2f-9a9a-xxxxxxxxxxxx"
}
```

### 任务查询与结果获取

- **查询任务状态**: `GET /api/task/{task_id}`
  - 返回字段：`status` (pending|processing|completed|failed), `progress` (0-100), `message`, `is_completed`
- **获取任务结果**: `GET /api/task/{task_id}/result`（任务完成后）
  - 成功结果示例：
```json
{
  "success": true,
  "document_path": "/abs/path/to/output/xxx.docx",
  "sections_count": 23,
  "download_link": "/api/download-document/xxx.docx"
}
```
- **下载生成文档**: `GET /api/download-document/{filename}`

### 请求示例

- **curl（带清单文件）**:
```bash
curl -X POST http://localhost:8000/api/generate-document \
  -F 'summary=这是文档总结内容，至少十个字符……' \
  -F 'outline_json={"title":"文档","sections":[{"title":"一、背景","sections":[]}]}' \
  -F 'style_template=A' \
  -F 'checklist_file=@/path/to/checklist.pdf'
```

- **curl（不带清单文件）**:
```bash
curl -X POST http://localhost:8000/api/generate-document \
  -F 'summary=这是文档总结内容，至少十个字符……' \
  -F 'outline_json={"title":"文档","sections":[]}' \
  -F 'style_template=B'
```

- **查询状态**:
```bash
curl http://localhost:8000/api/task/<task_id>
```

- **获取结果**:
```bash
curl http://localhost:8000/api/task/<task_id>/result
```

### 参数校验与错误

- **400 Bad Request**
  - 总结内容过短或为空：`"总结内容过短或为空"`
  - 缺少目录结构：`"缺少目录结构"`
  - 样式模板无效：`"样式模板无效，请从A, B, C, D, E中选择"`
  - 目录 JSON 无效：`"目录结构JSON格式无效"`
  - 清单文件格式不支持：`"清单文件格式不支持，仅支持.pdf .docx .xlsx .xls"`
  - 清单解析失败：`"清单文件解析失败: <原因>"`
- **500 Internal Server Error**
  - 服务内部异常：`{"success": false, "error": "<错误信息>"}`

### 重要说明

- **异步模式**: 提交后返回 `task_id`，请轮询状态并在完成后获取结果与下载链接。
- **目录结构建议**: 使用 `/api/generate-outline` 的返回值作为 `outline_json`。
- **清单合并规则**: 清单内容仅作参考整合，模型会根据章节标题与层级选择性融合，并非逐字拷贝。
- **结果有效期**: 任务与结果会定期清理，请在生成后尽快下载文档。