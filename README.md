# Coding AI — Agentic Code Assistant

A full-stack AI coding assistant that generates, tests, and iteratively improves Python code using a multi-agent LangGraph workflow. It features a React frontend, a FastAPI backend, PostgreSQL for persistence, and a secure Docker sandbox for isolated test execution.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Quick Start](#quick-start)
- [Running the Application](#running-the-application)
- [Docker Sandbox Setup](#docker-sandbox-setup)
- [API Overview](#api-overview)
- [Troubleshooting](#troubleshooting)

---

## Features

- **Agentic workflow** — Routes queries through a LangGraph state machine: classify intent → plan → generate code → run tests → reflect → re-plan → human review → final response
- **Secure sandboxed execution** — Generated code and tests run inside isolated Docker containers with CPU/memory limits and no network access
- **Persistent conversations** — Chat threads and messages stored in PostgreSQL; LangGraph checkpoints enable resumable multi-turn sessions
- **Human-in-the-loop** — The workflow pauses for user approval before finalising generated code
- **JWT authentication** — Register/login with bcrypt-hashed passwords and JWT access tokens
- **Dark/light theme** — Theme toggle with full Markdown rendering (including code blocks with syntax highlighting) in the chat UI

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                     │
│  Login / Register → Chat UI → Markdown renderer            │
└────────────────────────┬────────────────────────────────────┘
                         │  HTTP / Proxy (Vite → :8000)
┌────────────────────────▼────────────────────────────────────┐
│                    Backend (FastAPI)                        │
│                                                             │
│  ┌─────────┐  ┌──────────┐  ┌──────────────────────────┐  │
│  │  Auth   │  │  Users   │  │       Chatbot             │  │
│  │ Router  │  │  Router  │  │  Router + Sandbox Router  │  │
│  └─────────┘  └──────────┘  └────────────┬─────────────┘  │
│                                           │                 │
│                              ┌────────────▼──────────────┐ │
│                              │    LangGraph Workflow      │ │
│                              │                            │ │
│                              │  router → planner →        │ │
│                              │  coding → code_tester →    │ │
│                              │  reflection → re_planner → │ │
│                              │  human_review →            │ │
│                              │  final_response            │ │
│                              └────────────┬──────────────┘ │
└───────────────────────────────────────────┼─────────────────┘
                                            │
              ┌─────────────────────────────┼──────────────┐
              │                             │              │
   ┌──────────▼──────────┐    ┌────────────▼────────┐    │
   │  PostgreSQL          │    │  Docker Sandbox      │    │
   │  (chat history +     │    │  (isolated pytest    │    │
   │   LG checkpoints)    │    │   execution)         │    │
   └─────────────────────┘    └─────────────────────┘    │
                                            │              │
                               ┌────────────▼────────┐    │
                               │  LLM APIs            │    │
                               │  (xKiro / OpenRouter)│    │
                               └─────────────────────┘    │
```

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| Framework | FastAPI 0.139 |
| ASGI server | Uvicorn |
| Agent orchestration | LangGraph 1.2 + LangChain 1.3 |
| LLM integration | LangChain-OpenAI (OpenAI-compatible client) |
| Models used | `mistralai/codestral-2508` (coding), `minimax/minimax-m2.1-highspeed` (reasoning) |
| LLM gateway | xKiro API (`https://api.xkiro.com/v1`) |
| Conversation memory | LangGraph PostgreSQL checkpointer |
| Database ORM | SQLAlchemy 2 (async) |
| Database | PostgreSQL (via `asyncpg` + `psycopg`) |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt (pwdlib / argon2-cffi) |
| Validation | Pydantic v2 + pydantic-settings |
| Code sandbox | Docker SDK (`docker` Python package) |
| Fallback sandbox | Subprocess runner |
| HTTP client | httpx |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18 |
| Build tool | Vite 5 |
| Routing | React Router v6 |
| HTTP client | Axios |
| Markdown rendering | react-markdown + remark-gfm |
| Icons | lucide-react |
| Dev proxy | Vite proxy → FastAPI :8000 |

### Infrastructure
| Component | Technology |
|---|---|
| Containerised sandbox | Docker Desktop (Windows) / Docker Engine (Linux) |
| Sandbox base image | `python:3.11-slim` or custom `codecompletion-sandbox:latest` |
| Database | PostgreSQL 14+ |

---

## Project Structure

```
CodeCompletion/
├── backend/
│   ├── .env                    # ← secrets & config (never committed)
│   ├── main.py                 # FastAPI app entry point
│   ├── requirements.txt        # Python dependencies
│   ├── requirements-docker.txt # Extra deps for Docker SDK
│   ├── auth/                   # JWT auth (router, service, schemas)
│   ├── users/                  # User CRUD (model, repo, service, router)
│   ├── chatbot/                # Chat logic, LangGraph workflow, schemas
│   ├── core/                   # Config, database, security, logging
│   ├── middleware/             # CORS, exception, logging, timing
│   ├── prompts/                # All LLM prompt templates
│   └── sandbox/
│       ├── Dockerfile          # Custom sandbox image definition
│       ├── unified_runner.py   # Auto-selects Docker or subprocess
│       ├── docker_runner.py    # Docker-based isolated execution
│       ├── runner.py           # Subprocess-based execution (fallback)
│       └── setup_check.py      # Verifies sandbox setup
├── frontend/
│   ├── src/
│   │   ├── api/                # Axios wrappers (auth, chat, user)
│   │   ├── components/         # ChatArea, Sidebar, ProtectedRoute
│   │   ├── context/            # AuthContext, ThemeContext
│   │   └── pages/              # LoginPage, RegisterPage, ChatPage
│   ├── vite.config.js          # Dev server + proxy config
│   └── package.json
├── .gitignore
└── README.md
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Use a virtual environment |
| Node.js | 18+ | For the frontend |
| PostgreSQL | 14+ | Must be running before starting the backend |
| Docker Desktop | Latest | Required for the sandbox; optional in `subprocess` mode |

---

## Environment Variables

Create the file `backend/.env` (never commit it — it is in `.gitignore`).  
Use the template below and fill in your own values.

```env
# ── Application ───────────────────────────────────────────────
APP_NAME=Coding AI
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=True

# ── Database ──────────────────────────────────────────────────
# Format: postgresql+asyncpg://<user>:<password>@<host>:<port>/<dbname>
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/postgres

# ── Security ──────────────────────────────────────────────────
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=change-me-to-a-real-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=90

# ── CORS ──────────────────────────────────────────────────────
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:5173"]

# ── LLM API Keys ──────────────────────────────────────────────
# xKiro API — used for all LLM calls (coding model + reasoning model)
# Get your key at: https://xkiro.com  (or wherever your provider is)
XKIRO_API_KEY=your-xkiro-api-key-here

# OpenRouter API — alternative/fallback LLM gateway
# Get your key at: https://openrouter.ai/keys
OPENROUTER_API_KEY=your-openrouter-api-key-here

# ── Sandbox ───────────────────────────────────────────────────
# Mode: auto (Docker if available, else subprocess) | docker | subprocess
SANDBOX_MODE=auto
SANDBOX_TIMEOUT=30
SANDBOX_DOCKER_IMAGE=codecompletion-sandbox:latest
SANDBOX_MEMORY_LIMIT=512m
SANDBOX_CPU_QUOTA=100000
SANDBOX_ENABLE_NETWORK=false
```

### Where to get the API keys

| Key | Where to get it |
|---|---|
| `XKIRO_API_KEY` | Sign up at the xKiro platform. This key is used for **all LLM inference** — both the coding model (`codestral-2508`) and the reasoning/planning model. |
| `OPENROUTER_API_KEY` | Sign up at [openrouter.ai](https://openrouter.ai). Used as an alternative gateway if you swap the `base_url` in `graph_workflow.py`. |
| `SECRET_KEY` | Generate locally — run `python -c "import secrets; print(secrets.token_hex(32))"` and paste the output. |
| `DATABASE_URL` | Your local PostgreSQL connection string. Change `yourpassword`, host, port, and database name to match your setup. |

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/your-username/CodeCompletion.git
cd CodeCompletion
```

### 2. Set up the Python virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

If you plan to use the Docker sandbox (recommended):

```bash
pip install -r backend/requirements-docker.txt
```

### 4. Configure environment variables

```bash
# Copy the template and fill in your values
copy backend\.env.example backend\.env    # Windows
# cp backend/.env.example backend/.env   # macOS/Linux
```

Edit `backend/.env` — see the [Environment Variables](#environment-variables) section above.

### 5. Start PostgreSQL

Make sure your PostgreSQL server is running and the database exists. The app will auto-create tables on first startup via SQLAlchemy.

### 6. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

---

## Running the Application

### Backend

From the project root (with your venv active):

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### Frontend

In a separate terminal:

```bash
cd frontend
npm run dev
```

The app will be available at `http://localhost:3000`.  
The Vite dev server proxies all `/api` requests to the FastAPI backend automatically.

---

## Docker Sandbox Setup

The sandbox runs generated code in isolated Docker containers. It automatically falls back to a subprocess runner if Docker is unavailable.

### 1. Install Docker Desktop

Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) and start it.  
Verify it's working:

```bash
docker --version
docker ps
```

### 2. Build the custom sandbox image (recommended)

The custom image has all common packages pre-installed, which makes test runs significantly faster:

```bash
cd backend/sandbox
docker build -t codecompletion-sandbox:latest .
cd ../..
```

Make sure `SANDBOX_DOCKER_IMAGE=codecompletion-sandbox:latest` is set in `backend/.env`.

If you skip this step, set `SANDBOX_DOCKER_IMAGE=python:3.11-slim` and the runner will pull the base image on first use.

### 3. Verify setup

```bash
python backend/sandbox/setup_check.py
```

All checks should pass. If Docker is unavailable, the sandbox falls back to subprocess mode automatically (controlled by `SANDBOX_MODE=auto`).

### Sandbox modes

| Mode | Behaviour |
|---|---|
| `auto` | Uses Docker if available, falls back to subprocess |
| `docker` | Forces Docker — fails if Docker is not running |
| `subprocess` | Always uses subprocess — fastest for development |

---

## API Overview

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new user |
| `POST` | `/auth/login` | Login, returns JWT access token |
| `GET` | `/users/me` | Get current user profile |
| `GET` | `/chat/threads` | List all chat threads for current user |
| `POST` | `/chat/threads` | Create a new chat thread |
| `GET` | `/chat/threads/{id}/messages` | Get messages for a thread |
| `POST` | `/chat/threads/{id}/messages` | Send a message, triggers the LangGraph workflow |
| `POST` | `/chat/threads/{id}/resume` | Resume a paused workflow (human review approval) |
| `GET` | `/sandbox/status` | Get sandbox health and active runner info |
| `GET` | `/sandbox/health` | Simple sandbox health check |

Full interactive docs available at `http://localhost:8000/docs` when the backend is running.

---

## Troubleshooting

**`Cannot connect to Docker daemon`**  
Docker Desktop is not running. Start it from the system tray and wait for it to fully initialise.

**`ModuleNotFoundError` on backend startup**  
Your virtual environment is not activated, or dependencies are not installed. Run `pip install -r backend/requirements.txt` with the venv active.

**`Connection refused` on database startup**  
PostgreSQL is not running, or the `DATABASE_URL` in `backend/.env` is incorrect. Check your host, port, username, and password.

**Frontend shows a blank page or network errors**  
Ensure the backend is running on port 8000. The Vite proxy (`vite.config.js`) forwards `/api` → `http://localhost:8000`, so the backend must be up for any API calls to work.

**Sandbox always uses subprocess instead of Docker**  
Run `python backend/sandbox/setup_check.py` — it will report exactly which step is failing. Common causes: Docker Desktop not started, Docker SDK not installed (`pip install docker`), or image not built/pulled.

**LLM calls fail with 401 / 403**  
Check that `XKIRO_API_KEY` in `backend/.env` is valid and has enough credits. The same key is used for both the coding model and the planning/reasoning model.

**JWT errors (`Signature verification failed`)**  
`SECRET_KEY` in `backend/.env` has changed since the tokens were issued. This invalidates all existing tokens — users need to log in again.
