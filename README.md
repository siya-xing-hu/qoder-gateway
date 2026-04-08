<p align="center">
  <h1 align="center">⚡ Qoder Gateway</h1>
  <p align="center">OpenAI-compatible API gateway for Qoder CLI</p>
</p>

<p align="center">
  <strong>English</strong> | <a href="./README_CN.md">中文</a>
</p>

<p align="center">
  <a href="#-quick-start">Quick Start</a> •
  <a href="#-available-models">Models</a> •
  <a href="#-features">Features</a> •
  <a href="#-configuration">Configuration</a> •
  <a href="#-docker-deployment">Docker</a> •
  <a href="#-request-logs">Logs</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/OpenAI_Compatible-✔-green" alt="OpenAI Compatible">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
</p>

---

## 📖 What is Qoder Gateway?

Qoder Gateway is a lightweight proxy server that wraps the [Qoder CLI](https://qoder.com) behind an **OpenAI-compatible API**. This means any tool or application that works with the OpenAI API (Cursor, Continue, Open WebUI, etc.) can seamlessly work with Qoder — no code changes required.

```
┌──────────────┐     OpenAI API Format     ┌─────────────────┐     CLI     ┌───────────┐
│  Your Client │  ───────────────────────►  │  Qoder Gateway  │  ────────►  │ qodercli  │
│  (Cursor,..) │  ◄───────────────────────  │  :11435         │  ◄────────  │           │
└──────────────┘     SSE / JSON             └─────────────────┘             └───────────┘
```

---

## 🤖 Available Models

Qoder provides tiered models optimized for different use cases:

| Model | Tier | Description |
|-------|------|-------------|
| `lite` | Free | Simple Q&A, lightweight tasks |
| `efficient` | Low cost | Everyday coding, code completion |
| `auto` | Standard | Complex tasks, multi-step reasoning **(default)** |
| `performance` | High cost | Challenging engineering problems, large codebases |
| `ultimate` | Highest cost | Maximum performance, best possible results |

### Model Aliases

You can use familiar model names — they'll be automatically mapped:

<details>
<summary>📋 View all model aliases</summary>

| Alias | Maps to |
|-------|---------|
| `gpt-4`, `gpt-4o`, `claude-sonnet`, `claude-sonnet-4`, `claude-3.5-sonnet` | `auto` |
| `claude-opus`, `claude-opus-4`, `claude-3.5-opus` | `performance` |
| `claude-opus-4.5` | `ultimate` |
| `claude-haiku`, `claude-3.5-haiku`, `gpt-4o-mini` | `efficient` |
| `gpt-3.5-turbo` | `lite` |

</details>

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔄 **OpenAI Compatible** | Drop-in replacement for OpenAI API — works with any OpenAI client |
| 🌊 **Streaming Support** | Real-time Server-Sent Events (SSE) streaming responses |
| 🔑 **API Key Auth** | Secure gateway access with Bearer token authentication |
| 🔁 **Auto Retry** | Exponential backoff retry for 401, 429, and 5xx errors |
| 📊 **Request Logging** | All API requests logged to console and optionally to PostgreSQL |
| 🖥️ **Log Viewer** | Built-in web UI to browse and filter request logs |
| 🐳 **Docker Ready** | One-command deployment with Docker Compose (includes PostgreSQL) |
| 🏥 **Health Check** | Built-in `/health` endpoint for monitoring |

---

## 🚀 Quick Start

### Prerequisites

- **qodercli** — Install using one of the following methods:

  ```bash
  # cURL (macOS, Linux)
  curl -fsSL https://qoder.com/install | bash

  # Homebrew (macOS, Linux)
  brew install qoderai/qoder/qodercli --cask

  # NPM (macOS, Linux, Windows)
  npm install -g @qoder-ai/qodercli
  ```

  Verify installation:
  ```bash
  qodercli --version
  ```

- **Qoder Personal Access Token** — Get yours from [qoder.com/account/integrations](https://qoder.com/account/integrations)

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/your-username/qoder-gateway.git
cd qoder-gateway

# 2. Configure environment
cp .env.example .env
# Edit .env and set your QODER_PERSONAL_ACCESS_TOKEN and QODER_PROXY_API_KEY

# 3. Start (includes PostgreSQL for request logging)
docker-compose up -d
```

The gateway is now running at `http://localhost:11435`.

### Option 2: Run Locally

```bash
# 1. Clone and install dependencies
git clone https://github.com/your-username/qoder-gateway.git
cd qoder-gateway
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and set your tokens

# 3. Start the server
python main.py
```

### Test It

```bash
# Health check
curl http://localhost:11435/health

# List models
curl http://localhost:11435/v1/models \
  -H "Authorization: Bearer your-api-key"

# Chat completion
curl http://localhost:11435/v1/chat/completions \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "auto",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

---

## ⚙️ Configuration

All configuration is done through environment variables. Create a `.env` file from the example:

```bash
cp .env.example .env
```

### Authentication

| Variable | Description | Default |
|----------|-------------|---------|
| `QODER_PROXY_API_KEY` | API key that clients must provide to access this gateway | `my-qoder-secret-password-123` |
| `QODER_PERSONAL_ACCESS_TOKEN` | Your Qoder Personal Access Token | — |
| `QODER_CONFIG_FILE` | Path to Qoder CLI config file (alternative to token) | `~/.qoder.json` |

> 🔒 **Security**: Always change the default `QODER_PROXY_API_KEY` in production.

### Server

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVER_HOST` | Server bind address | `0.0.0.0` |
| `SERVER_PORT` | Server port | `11435` |
| `LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) | `INFO` |

### Timeouts & Retry

| Variable | Description | Default |
|----------|-------------|---------|
| `QODER_FIRST_TOKEN_TIMEOUT` | Timeout for first token (seconds) | `30` |
| `QODER_STREAMING_READ_TIMEOUT` | Streaming read timeout (seconds) | `300` |
| `QODER_FIRST_TOKEN_MAX_RETRIES` | Max retries for streaming requests | `3` |

### Workspace & Logging

| Variable | Description | Default |
|----------|-------------|---------|
| `QODER_WORKSPACE` | Working directory for qodercli — generated code is stored here | `/home/qoder/repo` |
| `LOG_DIR` | Log file output directory | `logs` |
| `DATABASE_URL` | PostgreSQL connection URL | — (logs to console only) |

> When using Docker Compose, `QODER_WORKSPACE`, `LOG_DIR` and `DATABASE_URL` are automatically configured. Generated code is mapped to `~/qoder/repo` on the host, and logs to `~/logs`.

---

## 🐳 Docker Deployment

### Volume Mounts

Docker Compose maps three directories between container and host:

| Container Path | Host Path | Description |
|---------------|-----------|-------------|
| `/app` | `.` (project dir) | Application source code — no rebuild needed on code changes |
| `/home/qoder/repo` | `~/qoder/repo` | Qoder-generated code workspace |
| `/home/qoder/logs` | `~/logs` | Application log files |

> **Tip**: Since the source code is mounted via volume, you only need `docker compose restart qoder-gateway` after code changes. Rebuild (`--build`) is only needed when `requirements.txt` changes.

### Architecture

```
docker-compose up -d
```

This starts two services:

| Service | Image | Description |
|---------|-------|-------------|
| `shared-postgres` | `postgres:16-alpine` | PostgreSQL database for request log persistence |
| `qoder-gateway` | Built from Dockerfile | The API gateway (port 11435) |

- **Shared network** (`shared-db`): Other projects can connect to the same PostgreSQL instance
- **Persistent volume** (`shared-pgdata`): Database data survives container restarts
- **Health checks**: Both services include health check configuration
- **Non-root user**: The gateway runs as user `qoder` for security

### Use Shared PostgreSQL in Other Projects

The PostgreSQL container uses a named network, so other projects can reuse it:

```yaml
# In another project's docker-compose.yml
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

### Customize PostgreSQL Credentials

Set these in your `.env` file before starting:

```bash
POSTGRES_USER=myuser
POSTGRES_PASSWORD=mysecretpassword
POSTGRES_DB=mydb
POSTGRES_PORT=5433
```

---

## 📊 Request Logs

When `DATABASE_URL` is configured (automatic with Docker Compose), all `/v1/` API requests are logged to PostgreSQL.

### Web Viewer

Browse logs at: **http://localhost:11435/logs**

Features:
- Filter by status code, path, and model
- Pagination support
- Click any row to expand and view request body and response details

### JSON API

```bash
# Get logs (paginated)
curl "http://localhost:11435/api/logs?page=1&page_size=20"

# Filter by status code
curl "http://localhost:11435/api/logs?status_code=200"

# Filter by model
curl "http://localhost:11435/api/logs?model=auto"

# Filter by path
curl "http://localhost:11435/api/logs?path=/v1/chat/completions"
```

### Logged Fields

| Field | Description |
|-------|-------------|
| `timestamp` | Request time (UTC) |
| `method` | HTTP method (GET, POST) |
| `path` | Request path |
| `status_code` | Response status code |
| `duration_ms` | Request duration in milliseconds |
| `client_ip` | Client IP address |
| `request_model` | Requested model name |
| `request_messages_count` | Number of messages in request |
| `request_stream` | Whether streaming was requested |
| `request_body` | Full request body (up to 10KB) |
| `response_summary` | Response body summary (up to 500 chars) |
| `error_message` | Error details if request failed |

---

## 🔌 API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | No | Health check |
| `GET` | `/health` | No | Detailed health status with timestamp |
| `GET` | `/v1/models` | Yes | List available models |
| `POST` | `/v1/chat/completions` | Yes | Chat completions (stream & non-stream) |
| `GET` | `/logs` | No | Web-based log viewer |
| `GET` | `/api/logs` | No | Log query API (JSON) |

### Chat Completions Request

```json
{
  "model": "auto",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Write a Python hello world"}
  ],
  "stream": true,
  "temperature": 0.7,
  "max_tokens": 1024
}
```

### Streaming Response (SSE)

```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"auto","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"auto","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1234567890,"model":"auto","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Web Framework | FastAPI |
| ASGI Server | Uvicorn |
| HTTP Client | httpx |
| Data Validation | Pydantic |
| Logging | Loguru |
| Database ORM | SQLAlchemy (async) |
| Database Driver | asyncpg |
| Template Engine | Jinja2 |
| Container | Docker + Docker Compose |
| Database | PostgreSQL 16 |

---

## 📁 Project Structure

```
qoder-gateway/
├── main.py                 # Application entry point
├── qoder/
│   ├── __init__.py
│   ├── auth.py             # Token authentication manager
│   ├── cli_client.py       # qodercli subprocess wrapper
│   ├── config.py           # Centralized configuration
│   ├── converters.py       # Request validation & format conversion
│   ├── database.py         # PostgreSQL logging (optional)
│   ├── http_client.py      # HTTP client with retry logic
│   ├── middleware.py        # Request/response logging middleware
│   ├── models.py           # Pydantic data models
│   ├── routes.py           # FastAPI route handlers
│   ├── streaming.py        # SSE stream format conversion
│   └── templates/
│       └── logs.html       # Log viewer web page
├── docker-compose.yml      # Docker orchestration
├── Dockerfile              # Container build config
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
└── .dockerignore
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
