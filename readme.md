# 🏛️ Nexus Council v2.0

[![Python](https://img.shields.io/badge/Python-3.10-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

> **Multi-Modal AI Research Orchestration Platform**

Nexus Council is a sophisticated autonomous "Council of Experts" system that mimics high-level human research and debate processes. It orchestrates multiple specialized AI agents to solve complex queries through parallel research, synthesis, and consensus-building.

---

## 🚀 What's New in v2.0

### Multi-Mode Operation
- **🏛️ Standard Council**: Parallel experts research single topic from different perspectives
- **🔬 Decomposition Mode**: Complex queries broken into sub-queries, researched in parallel, then synthesized
- **⚡ Quick Mode**: Direct LLM answers without web search for rapid responses

### Granular Configuration
- **Per-Role Model Selection**: Choose different models for Architect, Hunter, Analyst, and Moderator
- **Tone & Length Control**: Academic, Business, Technical, or Casual tones with variable output lengths
- **Search Toggle**: Enable/disable web search on demand

### Enhanced Dashboard
- **Clickable Session History**: Browse and reload past research sessions
- **Real-time Progress Tracking**: Visual progress bars and agent status indicators
- **Export Options**: Copy to clipboard, download JSON, or export Markdown reports
- **Persistent Results**: Results survive page refreshes and remain accessible

---

## 🎯 Capabilities

| Feature | Description |
|---------|-------------|
| **Autonomous Architecture** | AI "Architect" designs bespoke teams of 3-5 experts tailored to your prompt |
| **Parallel Research** | AI "Hunters" perform real-time web research simultaneously using Tavily and Trafilatura |
| **Local RAG** | High-speed local embeddings using `all-MiniLM-L6-v2` and `pgvector` for intelligent data retrieval |
| **Conflict Resolution** | "Moderator" analyzes expert reports to identify "Friction Points" and provide nuanced consensus |
| **Multi-Provider LLM Support** | AvalAI, Cloudflare, OpenRouter with dynamic model selection per role |
| **Real-time Dashboard** | Streamlit-based UI with session history, progress tracking, and result export |

---

## 🛠️ Tech Stack

### Backend
- **FastAPI**: High-performance async API framework
- **SQLAlchemy 2.0**: Async ORM with PostgreSQL
- **Pydantic V2**: Data validation and serialization
- **Celery + Redis**: Distributed task queue for parallel processing
- **pgvector**: Vector similarity search in PostgreSQL

### Intelligence Layer
- **Multi-Provider LLMs**: AvalAI, Cloudflare Workers AI, OpenRouter
- **Local Embeddings**: Sentence-Transformers (CPU-optimized)
- **Web Scraping**: Tavily API + Trafilatura for content extraction

### Frontend
- **Streamlit**: Interactive data apps with pure Python
- **Real-time Polling**: Live status updates without page refresh

### Infrastructure
- **Docker Compose**: Complete containerized stack
- **PostgreSQL 16 + pgvector**: Vector-enabled database
- **Redis**: Message broker and result backend

---

## 📦 Quick Start

### Prerequisites
- Docker and Docker Compose
- API keys for: AvalAI, Tavily, (optional) Cloudflare, OpenRouter

### 1. Clone and Configure

```bash
git clone https://github.com/yourusername/nexus-council.git
cd nexus-council

# Create environment file
cp .env.example .env

# Edit .env with your API keys
nano .env
```

### 2. Environment Variables

```env
# Required
AVALAI_API_KEY=your_avalai_key_here
TAVILY_API_KEY=your_tavily_key_here

# Optional (for additional providers)
CF_ACCOUNT_ID=your_cloudflare_account_id
CF_API_TOKEN=your_cloudflare_token
OPENROUTER_API_KEY=your_openrouter_key

# Infrastructure (defaults work with docker-compose)
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/nexus_council
REDIS_URL=redis://redis:6379/0
```

### 3. Launch

```bash
# Clean start (removes old data)
docker-compose down -v
docker-compose up --build -d

# View logs
docker-compose logs -f api worker
```

### 4. Access

- **Dashboard**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs
- **API**: http://localhost:8000

---

## 🎮 Usage Guide

### Standard Mode (Balanced Research)
1. Select "🏛️ Standard Council" mode
2. Enable web search for current data
3. Choose your preferred models per role
4. Enter a complex query
5. Track progress in real-time
6. Review consensus, friction points, and recommendations

### Decomposition Mode (Deep Investigation)
1. Select "🔬 Decomposition" mode
2. Set research angles (2-5 sub-queries)
3. Each angle gets parallel research
4. Final synthesis combines all findings
5. Best for broad topics requiring comprehensive coverage

### Quick Mode (Fast Answers)
1. Select "⚡ Quick Answer" mode
2. Web search automatically disabled
3. Single expert provides direct answer
4. Best for straightforward questions or when speed matters

---

## 🔧 Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Dashboard     │────▶│   FastAPI        │────▶│   PostgreSQL    │
│   (Streamlit)   │     │   (Orchestrator) │     │   + pgvector    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │                           │
                               ▼                           ▼
                        ┌──────────────┐          ┌──────────────┐
                        │    Celery    │          │   Knowledge  │
                        │    Workers   │          │   Storage    │
                        └──────────────┘          └──────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │    Redis     │
                        │   (Broker)   │
                        └──────────────┘
```

### Data Flow
1. **Request**: Dashboard → API creates `CouncilSession` with config
2. **Architect**: AI designs expert team based on mode and query
3. **Parallel Research**: Celery workers execute search + analysis concurrently
4. **Synthesis**: Moderator combines all reports into final output
5. **Storage**: Results persisted with full history and metadata

---

## 🌟 Performance Optimizations

- **CPU-Optimized Docker**: Custom build logic prevents WSL2 crashes with CPU-only Torch
- **WSL2 Networking**: Custom MTU settings prevent SSL/EOF connection errors
- **Model Caching**: Pre-downloaded embeddings in Docker image layer
- **Connection Pooling**: Async SQLAlchemy with proper session management
- **Rate Limiting**: Celery task rate limits prevent API throttling

---

## 🐛 Troubleshooting

### Common Issues

**Issue**: `Moderation failed: 'list' object has no attribute 'get'`
- **Fix**: Update to latest version - LLM response parsing now handles arrays gracefully

**Issue**: Workers fail to connect to PostgreSQL
- **Fix**: Ensure `DATABASE_URL` uses `postgres` hostname (not localhost) in Docker

**Issue**: Embedding model not found
- **Fix**: Model is pre-downloaded in Dockerfile; check volume mounts in docker-compose.yml

**Issue**: API returns 422 validation errors
- **Fix**: Ensure dashboard and backend schemas match (see `app/schemas/api.py`)

### Debug Mode

```bash
# View detailed logs
docker-compose logs -f worker | grep -E "(ERROR|INFO|Agent)"

# Check database
docker-compose exec postgres psql -U postgres -d nexus_council -c "SELECT id, status, mode FROM council_sessions ORDER BY created_at DESC LIMIT 5;"

# Restart specific service
docker-compose restart worker
```

---

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Additional LLM providers (Anthropic, OpenAI, local models)
- Enhanced embedding models
- WebSocket support for real-time updates
- Persistent session storage (currently in-memory only)
- Multi-language support

---


## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/)
- [Streamlit](https://streamlit.io/)
- [Sentence-Transformers](https://www.sbert.net/)
- [Tavily](https://tavily.com/)

---