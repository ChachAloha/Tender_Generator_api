# 模型配置管理 API 文档

## 概述

模型配置管理 API 提供了对 AI 模型配置的完整 CRUD 操作，包括创建、查询、更新、激活和删除模型配置。所有配置都支持不同的 AI 服务提供商（如 OpenAI、DeepSeek 等），并在创建和更新时自动验证模型是否支持 JSON 格式输出。

**基础路径**: `/api`  
**标签**: `model-configs`

## 数据模型

### ModelConfigCreate
创建模型配置时使用的数据模型：

```json
{
  "name": "string",           // 必需：配置名称，便于区分用途
  "base_url": "string",       // 必需：模型服务的 Base URL
  "model": "string",          // 必需：模型名称或标识
  "api_key": "string",        // 必需：访问模型服务的 API Key
  "is_active": false          // 可选：是否设为激活配置，默认 false
}
```

### ModelConfigUpdate
更新模型配置时使用的数据模型（所有字段都是可选的）：

```json
{
  "name": "string",           // 可选：配置名称
  "base_url": "string",       // 可选：模型服务 Base URL
  "model": "string",          // 可选：模型名称或标识
  "api_key": "string"         // 可选：API Key
}
```

## API 端点

### 1. 获取模型配置列表

**GET** `/api/model-configs`

获取所有已保存的模型配置列表，API Key 字段已脱敏处理。

#### 请求参数
无

#### 响应示例
```json
{
  "success": true,
  "items": [
    {
      "id": "config_123456",
      "name": "DeepSeek Chat",
      "base_url": "https://api.deepseek.com/v1",
      "model": "deepseek-chat",
      "api_key_masked": "sk-***",
      "is_active": true,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": "config_789012",
      "name": "OpenAI GPT-4",
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-4",
      "api_key_masked": "sk-***",
      "is_active": false,
      "created_at": "2024-01-14T15:20:00Z",
      "updated_at": "2024-01-14T15:20:00Z"
    }
  ]
}
```

---

### 2. 创建模型配置

**POST** `/api/model-configs`

创建新的模型配置。创建前会自动验证模型是否支持 JSON 格式输出。

#### 请求体
```json
{
  "name": "我的 DeepSeek 配置",
  "base_url": "https://api.deepseek.com/v1",
  "model": "deepseek-chat",
  "api_key": "sk-your-api-key-here",
  "is_active": true
}
```

#### 响应示例
```json
{
  "success": true,
  "item": {
    "id": "config_345678",
    "name": "我的 DeepSeek 配置",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "is_active": true
  }
}
```

#### 错误响应
```json
{
  "detail": "模型不支持 JSON response_format 或配置无效：具体错误信息"
}
```

**状态码**:
- `200`: 创建成功
- `422`: 参数校验失败或模型不支持 JSON 格式

---

### 3. 更新模型配置

**PATCH** `/api/model-configs/{config_id}`

根据配置 ID 局部更新模型配置，未提供的字段保持不变。更新前会验证新配置是否支持 JSON 格式输出。

#### 路径参数
- `config_id` (string): 配置 ID

#### 请求体
```json
{
  "name": "更新后的配置名称",
  "model": "gpt-4-turbo"
}
```

#### 响应示例
```json
{
  "success": true,
  "item": {
    "id": "config_345678",
    "name": "更新后的配置名称",
    "base_url": "https://api.deepseek.com/v1",
    "model": "gpt-4-turbo",
    "is_active": false
  }
}
```

**状态码**:
- `200`: 更新成功
- `404`: 配置不存在
- `422`: 模型不支持 JSON 格式

---

### 4. 激活模型配置

**POST** `/api/model-configs/{config_id}/activate`

将指定配置设置为当前激活配置。系统同时只能有一个激活配置。

#### 路径参数
- `config_id` (string): 配置 ID

#### 请求体
无

#### 响应示例
```json
{
  "success": true,
  "item": {
    "id": "config_345678",
    "name": "我的 DeepSeek 配置",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "is_active": true
  }
}
```

**状态码**:
- `200`: 切换成功
- `404`: 配置不存在

---

### 5. 删除模型配置

**DELETE** `/api/model-configs/{config_id}`

根据配置 ID 删除模型配置。

#### 路径参数
- `config_id` (string): 配置 ID

#### 请求体
无

#### 响应示例
```json
{
  "success": true
}
```

**状态码**:
- `200`: 删除成功
- `404`: 配置不存在或已删除


### cURL 示例

```bash
# 1. 创建配置
curl -X POST "http://localhost:8000/api/model-configs" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试配置",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "api_key": "sk-your-api-key",
    "is_active": true
  }'

# 2. 获取配置列表
curl -X GET "http://localhost:8000/api/model-configs"

# 3. 更新配置
curl -X PATCH "http://localhost:8000/api/model-configs/config_123456" \
  -H "Content-Type: application/json" \
  -d '{"name": "更新后的配置名称"}'

# 4. 激活配置
curl -X POST "http://localhost:8000/api/model-configs/config_123456/activate"

# 5. 删除配置
curl -X DELETE "http://localhost:8000/api/model-configs/config_123456"
```