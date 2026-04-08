<p align="center">
  <h1 align="center">⚡ Qoder Gateway</h1>
  <p align="center">兼容 OpenAI API 的 Qoder CLI 网关</p>
</p>

<p align="center">
  <a href="./README.md">English</a> | <strong>中文</strong>
</p>

<p align="center">
  <a href="#-快速开始">快速开始</a> •
  <a href="#-可用模型">模型</a> •
  <a href="#-功能特性">特性</a> •
  <a href="#-配置说明">配置</a> •
  <a href="#-docker-部署">Docker</a> •
  <a href="#-请求日志">日志</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/OpenAI_兼容-✔-green" alt="OpenAI Compatible">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
</p>

---

## 📖 简介

Qoder Gateway 是一个轻量级代理服务器，将 [Qoder CLI](https://qoder.com) 包装为 **OpenAI 兼容的 API**。这意味着任何支持 OpenAI API 的工具或应用（Cursor、Continue、Open WebUI 等）都可以无缝接入 Qoder，无需修改代码。

```
┌──────────────┐     OpenAI API 格式      ┌─────────────────┐     CLI     ┌───────────┐
│   你的客户端   │  ───────────────────────►  │  Qoder Gateway  │  ────────►  │ qodercli  │
│  (Cursor,..) │  ◄───────────────────────  │  :11435         │  ◄────────  │           │
└──────────────┘     SSE / JSON            └─────────────────┘             └───────────┘
```

---

## 🤖 可用模型

Qoder 提供分层模型，适用于不同场景：

| 模型 | 层级 | 说明 |
|------|------|------|
| `lite` | 免费 | 简单问答、轻量任务 |
| `efficient` | 低成本 | 日常编程、代码补全 |
| `auto` | 标准 | 复杂任务、多步推理 **（默认）** |
| `performance` | 高成本 | 高难度工程问题、大型代码库 |
| `ultimate` | 最高成本 | 最高性能、最佳效果 |

### 模型别名

你可以使用熟悉的模型名称，系统会自动映射：

<details>
<summary>📋 查看所有模型别名</summary>

| 别名 | 映射到 |
|------|--------|
| `gpt-4`、`gpt-4o`、`claude-sonnet`、`claude-sonnet-4`、`claude-3.5-sonnet` | `auto` |
| `claude-opus`、`claude-opus-4`、`claude-3.5-opus` | `performance` |
| `claude-opus-4.5` | `ultimate` |
| `claude-haiku`、`claude-3.5-haiku`、`gpt-4o-mini` | `efficient` |
| `gpt-3.5-turbo` | `lite` |

</details>

---

## ✨ 功能特性

| 特性 | 说明 |
|------|------|
| 🔄 **OpenAI 兼容** | 可直接替代 OpenAI API，适配任何 OpenAI 客户端 |
| 🌊 **流式响应** | 支持 Server-Sent Events (SSE) 实时流式输出 |
| 🔑 **API Key 认证** | 通过 Bearer Token 保护网关访问 |
| 🔁 **自动重试** | 对 401、429、5xx 错误使用指数退避重试 |
| 📊 **请求日志** | 所有 API 请求记录到控制台，可选持久化到 PostgreSQL |
| 🖥️ **日志查看器** | 内置 Web 界面，浏览和筛选请求日志 |
| 🐳 **Docker 就绪** | 一条命令部署，Docker Compose 包含 PostgreSQL |
| 🏥 **健康检查** | 内置 `/health` 端点用于监控 |

---

## 🚀 快速开始

### 前置条件

- **qodercli** — 通过以下方式安装：

  ```bash
  # cURL（macOS、Linux）
  curl -fsSL https://qoder.com/install | bash

  # Homebrew（macOS、Linux）
  brew install qoderai/qoder/qodercli --cask

  # NPM（macOS、Linux、Windows）
  npm install -g @qoder-ai/qodercli
  ```

  验证安装：
  ```bash
  qodercli --version
  ```

- **Qoder 个人访问令牌** — 在 [qoder.com/account/integrations](https://qoder.com/account/integrations) 获取

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/qoder-gateway.git
cd qoder-gateway

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，设置 QODER_PERSONAL_ACCESS_TOKEN 和 QODER_PROXY_API_KEY

# 3. 启动（自动包含 PostgreSQL 用于请求日志记录）
docker-compose up -d
```

网关现在运行在 `http://localhost:11435`。

### 方式二：本地运行

```bash
# 1. 克隆并安装依赖
git clone https://github.com/your-username/qoder-gateway.git
cd qoder-gateway
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，设置你的令牌

# 3. 启动服务
python main.py
```

### 测试一下

```bash
# 健康检查
curl http://localhost:11435/health

# 获取模型列表
curl http://localhost:11435/v1/models \
  -H "Authorization: Bearer your-api-key"

# 聊天补全
curl http://localhost:11435/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "你好！"}],
    "stream": false
  }'
```

---

## ⚙️ 配置说明

所有配置通过环境变量完成。从示例文件创建 `.env`：

```bash
cp .env.example .env
```

### 认证配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QODER_PROXY_API_KEY` | 客户端访问网关所需的 API Key | `my-qoder-secret-password-123` |
| `QODER_PERSONAL_ACCESS_TOKEN` | 你的 Qoder 个人访问令牌 | — |
| `QODER_CONFIG_FILE` | Qoder CLI 配置文件路径（令牌的替代方案） | `~/.qoder.json` |

> 🔒 **安全提示**：生产环境中请务必修改默认的 `QODER_PROXY_API_KEY`。

### 服务器配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SERVER_HOST` | 服务器监听地址 | `0.0.0.0` |
| `SERVER_PORT` | 服务器端口 | `11435` |
| `LOG_LEVEL` | 日志级别（DEBUG、INFO、WARNING、ERROR） | `INFO` |

### 超时与重试

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QODER_FIRST_TOKEN_TIMEOUT` | 首个 Token 超时时间（秒） | `30` |
| `QODER_STREAMING_READ_TIMEOUT` | 流式读取超时时间（秒） | `300` |
| `QODER_FIRST_TOKEN_MAX_RETRIES` | 流式请求最大重试次数 | `3` |

### 工作区与日志

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `QODER_WORKSPACE` | qodercli 工作目录 — 生成的代码存放在此 | `/home/qoder/repo` |
| `LOG_DIR` | 日志文件输出目录 | `logs` |
| `DATABASE_URL` | PostgreSQL 连接 URL | —（仅输出到控制台） |

> 使用 Docker Compose 时，`QODER_WORKSPACE`、`LOG_DIR` 和 `DATABASE_URL` 会自动配置。生成的代码映射到宿主机 `~/qoder/repo`，日志映射到 `~/logs`。

---

## 🐳 Docker 部署

### 目录挂载

Docker Compose 在容器和宿主机之间映射了三个目录：

| 容器内路径 | 宿主机路径 | 用途 |
|-----------|-----------|------|
| `/app` | `.`（项目目录） | 应用源代码 — 修改代码无需重新构建镜像 |
| `/home/qoder/repo` | `~/qoder/repo` | Qoder 生成的代码工作区 |
| `/home/qoder/logs` | `~/logs` | 应用日志文件 |

> **提示**：由于源代码通过 volume 挂载，修改代码后只需 `docker compose restart qoder-gateway` 即可生效。仅当 `requirements.txt` 变更时才需要重新构建（`--build`）。

### 架构

```bash
docker-compose up -d
```

启动两个服务：

| 服务 | 镜像 | 说明 |
|------|------|------|
| `shared-postgres` | `postgres:16-alpine` | PostgreSQL 数据库，用于请求日志持久化 |
| `qoder-gateway` | 基于 Dockerfile 构建 | API 网关（端口 11435） |

- **共享网络**（`shared-db`）：其他项目可以连接同一个 PostgreSQL 实例
- **持久化卷**（`shared-pgdata`）：数据库数据在容器重启后不丢失
- **健康检查**：两个服务均配置了健康检查
- **非 root 用户**：网关以 `qoder` 用户运行，确保安全

### 在其他项目中复用 PostgreSQL

PostgreSQL 容器使用命名网络，其他项目可以直接复用：

```yaml
# 在另一个项目的 docker-compose.yml 中
services:
  my-app:
    # ...
    environment:
      - DATABASE_URL=postgresql://postgres:password123@shared-postgres:5432/my_other_db
    networks:
      - shared-db

networks:
  shared-db:
    external: true
    name: shared-db
```

### 自定义 PostgreSQL 凭据

在启动前，在 `.env` 文件中设置：

```bash
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mysecretpassword
POSTGRES_DB=mydb
POSTGRES_PORT=5433
```

---

## 📊 请求日志

当配置了 `DATABASE_URL` 时（Docker Compose 自动配置），所有 `/v1/` API 请求会被记录到 PostgreSQL。

### Web 查看器

在浏览器中打开：**http://localhost:11435/logs**

功能：
- 按状态码、路径、模型筛选
- 分页浏览
- 点击行可展开查看请求体和响应详情

### JSON API

```bash
# 获取日志（分页）
curl "http://localhost:11435/api/logs?page=1&page_size=20"

# 按状态码筛选
curl "http://localhost:11435/api/logs?status_code=200"

# 按模型筛选
curl "http://localhost:11435/api/logs?model=auto"

# 按路径筛选
curl "http://localhost:11435/api/logs?path=/v1/chat/completions"
```

### 记录字段

| 字段 | 说明 |
|------|------|
| `timestamp` | 请求时间（UTC） |
| `method` | HTTP 方法（GET、POST） |
| `path` | 请求路径 |
| `status_code` | 响应状态码 |
| `duration_ms` | 请求耗时（毫秒） |
| `client_ip` | 客户端 IP 地址 |
| `request_model` | 请求的模型名称 |
| `request_messages_count` | 请求中的消息数量 |
| `request_stream` | 是否为流式请求 |
| `request_body` | 完整请求体（最大 10KB） |
| `response_summary` | 响应体摘要（最大 500 字符） |
| `error_message` | 请求失败时的错误详情 |

---

## 🔌 API 端点

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| `GET` | `/` | 否 | 健康检查 |
| `GET` | `/health` | 否 | 详细健康状态（含时间戳） |
| `GET` | `/v1/models` | 是 | 获取可用模型列表 |
| `POST` | `/v1/chat/completions` | 是 | 聊天补全（支持流式和非流式） |
| `GET` | `/logs` | 否 | Web 日志查看器 |
| `GET` | `/api/logs` | 否 | 日志查询 API（JSON） |

### 聊天补全请求示例

```json
{
  "model": "auto",
  "messages": [
    {"role": "system", "content": "你是一个有用的助手。"},
    {"role": "user", "content": "用 Python 写一个 Hello World"}
  ],
  "stream": true,
  "temperature": 0.7,
  "max_tokens": 1024
}
```

### 流式响应示例（SSE）

```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"auto","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"auto","choices":[{"index":0,"delta":{"content":"你好"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"auto","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

---

## 🛠️ 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| ASGI 服务器 | Uvicorn |
| HTTP 客户端 | httpx |
| 数据验证 | Pydantic |
| 日志管理 | Loguru |
| 数据库 ORM | SQLAlchemy（异步） |
| 数据库驱动 | asyncpg |
| 模板引擎 | Jinja2 |
| 容器化 | Docker + Docker Compose |
| 数据库 | PostgreSQL 16 |

---

## 📁 项目结构

```
qoder-gateway/
├── main.py                 # 应用入口
├── qoder/
│   ├── __init__.py
│   ├── auth.py             # 令牌认证管理
│   ├── cli_client.py       # qodercli 子进程封装
│   ├── config.py           # 集中式配置管理
│   ├── converters.py       # 请求验证与格式转换
│   ├── database.py         # PostgreSQL 日志存储（可选）
│   ├── http_client.py      # HTTP 客户端（含重试逻辑）
│   ├── middleware.py        # 请求/响应日志中间件
│   ├── models.py           # Pydantic 数据模型
│   ├── routes.py           # FastAPI 路由处理
│   ├── streaming.py        # SSE 流格式转换
│   └── templates/
│       └── logs.html       # 日志查看页面
├── docker-compose.yml      # Docker 编排配置
├── Dockerfile              # 容器构建配置
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
└── .dockerignore
```

---

## 📄 许可证

本项目基于 MIT 许可证开源 — 详情请查看 [LICENSE](LICENSE) 文件。
