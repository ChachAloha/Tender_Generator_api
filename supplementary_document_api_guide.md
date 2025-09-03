调用流程分为以下四个主要步骤：

1.  **发起生成任务**: 通过 `POST` 请求提交文档总结和用户需求，API会创建一个后台任务并立即返回一个 `task_id`。
2.  **轮询任务状态**: 使用上一步获取的 `task_id`，通过 `GET` 请求轮询任务状态接口，直到任务状态变为 `completed`。
3.  **获取任务结果**: 任务完成后，通过 `GET` 请求访问结果接口，获取包含下载链接在内的详细信息。
4.  **下载文档**: 使用结果中的下载链接，通过 `GET` 请求下载生成的Word文档。

---

## 详细步骤

### 第1步：发起补充文档生成任务

首先，您需要向 `/api/generate-supplementary-document` 端点发起一个 `POST` 请求。

-   **Method**: `POST`
-   **URL**: `/api/generate-supplementary-document`
-   **Body**: `multipart/form-data`

#### 参数说明

| 参数名           | 类型   | 是否必须 | 描述                                                         |
| ---------------- | ------ | -------- | ------------------------------------------------------------ |
| `summary`        | `string` | 是       | 原始文档的总结内容，建议长度大于10个字符。                   |
| `user_request`   | `string` | 是       | 用户的具体补充需求，例如“请详细说明项目的技术实现细节”，建议长度大于5个字符。 |
| `style_template` | `string` | 否       | 文档的样式模板，可选值为 `'A', 'B', 'C', 'D', 'E'`。默认为 `'A'`。 |

#### cURL 请求示例

```bash
curl -X POST http://127.0.0.1:8000/api/generate-supplementary-document \
-F "summary=这是一个关于某项目系统设计的总结，主要涵盖了总体架构、核心模块和部署策略。" \
-F "user_request=请详细补充其中关于数据库选型和高可用性方案的论证过程。" \
-F "style_template=B"
```

#### 成功响应

如果请求成功，API将返回一个JSON对象，其中包含任务ID。

```json
{
    "success": true,
    "message": "补充文档生成任务已创建",
    "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef"
}
```

请务必保存好返回的 `task_id`，后续步骤将需要它。

### 第2步：查询任务状态

在获取 `task_id` 后，您需要定期（例如每隔几秒）调用任务状态查询接口，以了解任务的实时进展。

-   **Method**: `GET`
-   **URL**: `/api/task/{task_id}`

#### cURL 请求示例

将 `{task_id}` 替换为您在上一步中获取到的实际ID。

```bash
curl -X GET http://127.0.0.1:8000/api/task/a1b2c3d4-e5f6-7890-1234-567890abcdef
```

#### 响应示例

响应会显示任务的当前状态 (`status`)、进度 (`progress`) 和状态信息 (`message`)。

```json
{
    "success": true,
    "task_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
    "status": "processing", // 可能的状态: pending, processing, completed, failed
    "progress": 50,
    "message": "开始生成补充文档",
    "is_completed": false
}
```

当 `status` 变为 `completed` 并且 `is_completed` 为 `true` 时，表示任务已成功完成，您可以进行下一步。

### 第3步：获取任务结果

任务完成后，调用结果获取接口来检索生成的文档信息。

-   **Method**: `GET`
-   **URL**: `/api/task/{task_id}/result`

#### cURL 请求示例

```bash
curl -X GET http://127.0.0.1:8000/api/task/a1b2c3d4-e5f6-7890-1234-567890abcdef/result
```

#### 成功响应

响应将包含生成的文档路径、纯文本内容以及最重要的**下载链接**。

```json
{
    "success": true,
    "document_path": "/app/output/supplementary_document_1678886400.docx",
    "plain_text": "这是生成的补充文档的纯文本内容...",
    "sections_count": 5,
    "download_link": "/api/download-document/supplementary_document_1678886400.docx"
}
```

如果任务尚未完成，您会收到一个错误提示。

### 第4步：下载生成的文档

最后，使用上一步获取的 `download_link` 来下载生成的 `.docx` 文件。

-   **Method**: `GET`
-   **URL**: `http://<your-api-host>{download_link}`

#### cURL 请求示例

使用 `download_link` 的路径，并使用 `-o` 选项将文件保存到本地。

```bash
curl -X GET http://127.0.0.1:8000/api/download-document/supplementary_document_1678886400.docx -o my_supplementary_document.docx
```

执行此命令后，名为 `my_supplementary_document.docx` 的文件将被下载到您当前的目录中。

---
