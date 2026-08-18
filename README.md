# AgentMason AI Platform

AgentMason AI Platform is an enterprise-grade AI agent framework designed as a foundation for consulting engagements, internal copilots, knowledge assistants, and regulated government technology solutions.

## Highlights

- Clean architecture with domain-driven packages
- Security-first design with JWT auth, RBAC, and API keys
- Multi-provider LLM support via OpenAI, Anthropic, Google Gemini, Azure OpenAI, and Ollama
- RAG pipeline with document ingestion, chunking, embeddings, vector search, and citations
- Business Memory — persistent long-term knowledge about your business
- Business Graph — entity and relationship mapping for organizational intelligence
- Prompt management, evaluation, tracing, and observability
- Docker-based deployment and CI/CD workflow

## Architecture

```mermaid
flowchart LR
  User[Users] --> Web[Next.js Web App]
  Web --> API[FastAPI API]
  API --> Agents[Agent Framework]
  API --> RAG[RAG Pipeline]
  API --> Memory[Business Memory]
  API --> Graph[Business Graph]
  Agents --> LLM[LLM Providers]
  RAG --> Vector[(Vector Stores)]
  Memory --> DB[(PostgreSQL)]
  Graph --> DB
  API --> DB
  API --> Cache[(Redis)]
```

## Prerequisites

- **Python 3.9+** (tested with 3.13)
- **Node.js 18+** (for the Next.js frontend)
- **PostgreSQL 16** (or use SQLite for local development — default)
- **Redis 7** (optional, for caching)

## Running the Application

### Option 1: Docker Compose (recommended for full stack)

```bash
docker compose up
```

This starts:
- API at http://localhost:8000
- Web UI at http://localhost:3000
- PostgreSQL at localhost:5432
- Redis at localhost:6379

### Option 2: Local Development (no Docker required)

#### Backend (API Server)

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -e .
pip install python-multipart  # Required for file uploads

# 3. Start the API server (uses SQLite by default)
uvicorn apps.api.app.main:app --reload --port 8000
```

The API server will create a local `agentmason.db` SQLite file automatically.

#### Backend with HTTPS

```bash
# Generate a self-signed certificate for localhost
mkdir -p certs
openssl req -x509 -newkey rsa:2048 \
  -keyout certs/key.pem -out certs/cert.pem \
  -days 365 -nodes -subj "/CN=localhost"

# Start with HTTPS
uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000 \
  --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem
```

API will be available at `https://localhost:8000`. Your browser will warn about the self-signed cert — accept the warning to proceed.

#### Frontend (Next.js Web App)

```bash
cd apps/web

# Install dependencies (use --legacy-peer-deps if you see ERESOLVE errors)
npm install --legacy-peer-deps

# Start the dev server
npm run dev
```

Frontend will be available at `http://localhost:3000`.

#### Quick Start (both servers)

```bash
# Terminal 1 — Backend
source .venv/bin/activate
rm -f agentmason.db
uvicorn apps.api.app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd apps/web
npm install --legacy-peer-deps
npm run dev
```

### Option 3: With PostgreSQL

```bash
# Set environment variables (or create a .env file)
export DATABASE_URL="postgresql+psycopg://agentmason:agentmason@localhost:5432/agentmason"
export REDIS_URL="redis://localhost:6379/0"
export JWT_SECRET_KEY="your-secret-key"

# Run database migrations
alembic upgrade head

# Start the server
uvicorn apps.api.app.main:app --reload --port 8000
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./agentmason.db` | Database connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `JWT_SECRET_KEY` | `change-me` | JWT signing secret (change in production) |
| `OPENAI_API_KEY` | (empty) | OpenAI API key for LLM and embeddings |
| `ANTHROPIC_API_KEY` | (empty) | Anthropic API key for Claude models |

### Verify It Works

```bash
# Health check
curl http://localhost:8000/health
# → {"status":"ok","service":"api"}

# Register a user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"YourPass123","name":"Your Name"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"YourPass123"}'
# → {"access_token":"eyJ...","token_type":"bearer","expires_in":3600}
```

## API Endpoints

### Core
- `GET /health` — Health check
- `POST /auth/register` — Register user
- `POST /auth/login` — Login (returns JWT)
- `GET /me` — Current user info

### Knowledge (RAG)
- `POST /api/knowledge/documents` — Upload document
- `GET /api/knowledge/documents` — List documents
- `GET /api/knowledge/search?q=query` — Semantic search

### Business Memory
- `GET /api/memory` — List memories (supports `?q=`, `?category=`, `?status=`)
- `POST /api/memory` — Create memory
- `GET /api/memory/{id}` — Get memory
- `PATCH /api/memory/{id}` — Update memory
- `DELETE /api/memory/{id}` — Delete memory

### Business Graph
- `GET /api/graph/entities` — List entities (supports `?q=`, `?entity_type=`)
- `POST /api/graph/entities` — Create entity
- `GET /api/graph/entities/{id}` — Get entity
- `GET /api/graph/entities/{id}/relationships` — Get entity relationships
- `GET /api/graph/entities/{id}/related?depth=N` — Graph traversal
- `POST /api/graph/relationships` — Create relationship
- `DELETE /api/graph/relationships/{id}` — Delete relationship

### Integrations
- `GET /api/integrations` — List connected integrations
- `POST /api/integrations/{provider}/connect` — Start OAuth flow

### Agents
- `POST /agents/run` — Execute an agent
- `POST /agents/stream` — Stream agent response

## Running Tests

```bash
source .venv/bin/activate
pip install pytest httpx

# Run all tests
pytest tests/ -v

# Run Phase 5 tests specifically
pytest tests/test_memory_graph.py -v
```

## Web UI

The frontend runs at http://localhost:3000 and includes:
- **Business Memory** (`/memory`) — View, search, create, and manage business memories
- **Business Graph** (`/graph`) — Explore entities and relationships

## Deployment

Use Docker Compose for local deployment or Kubernetes manifests in the infra directory for production rollout.
