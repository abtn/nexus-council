# 🏛️ Nexus Council v2.1

[![Python](https://img.shields.io/badge/Python-3.10-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)

> **Resilient Multi-Modal AI Research Orchestration Platform**

Nexus Council is an advanced autonomous system that orchestrates a "Council of Experts" to solve complex queries. It utilizes parallel asynchronous agents to perform research, synthesis, and consensus-building, with robust error handling and multi-provider support.

---

## 🚀 What's New in v2.1

### 🛡️ Enhanced Resilience & Compatibility
*   **Universal LLM Support:** Refactored provider architecture (`OpenAIStrategy`) to support any OpenAI-compatible API (AvalAI, OpenRouter, vLLM) with a single codebase.
*   **Intelligent Fallbacks:**
    *   **JSON Mode Fallback:** If a provider doesn't support structured JSON (e.g., Cloudflare), the system automatically switches to prompt engineering to extract structured data.
    *   **System Role Fallback:** If a model rejects the `system` role (e.g., AvalAI Gemma), the system automatically merges instructions into the user prompt.
*   **VPN/Anti-Scraping Resilience:** Updated scraping logic to use browser spoofing headers, significantly reducing `403 Forbidden` errors when operating behind VPNs or restricted networks.

### 🎛️ Dashboard Improvements
*   **Session History:** Browse and reload previous research sessions directly from the UI.
*   **Granular Control:** Select different models for specific roles (Architect, Hunter, Analyst, Moderator).

---

## 🎯 Capabilities

| Feature | Description |
|---------|-------------|
| **Autonomous Architecture** | AI "Architect" dynamically assembles a team of 3-5 experts tailored to your query (Standard, Decomposition, or Quick modes). |
| **Parallel Research** | Agents research simultaneously using Tavily search and Trafilatura scraping. |
| **Local RAG** | High-performance vector search using `pgvector` and `sentence-transformers` for context retrieval. |
| **Conflict Resolution** | "Moderator" analyzes conflicting reports to identify "Friction Points" and build a final consensus. |
| **Multi-Provider Strategy** | Seamlessly routes requests between AvalAI, Cloudflare Workers AI, and OpenRouter based on availability and capability. |

---

## 🛠️ Tech Stack

### Backend
*   **FastAPI:** High-performance async web framework.
*   **SQLAlchemy 2.0:** Async ORM with PostgreSQL.
*   **ARQ:** Fast, async job queue built on Redis (replacing Celery for pure Python async performance).
*   **pgvector:** Vector similarity search extension for PostgreSQL.

### Intelligence Layer
*   **LLM Providers:** AvalAI (Gemma, Flash), Cloudflare (Llama 3), OpenRouter.
*   **Instructor:** Structured output generation library (with custom fallbacks).
*   **Embeddings:** `sentence-transformers` (CPU-optimized).

### Frontend
*   **Streamlit:** Real-time interactive dashboard with session management.

### Infrastructure
*   **Docker Compose:** Complete containerized deployment.
*   **Redis:** Message broker and caching layer.

---

## 📦 Quick Start

### Prerequisites
*   Docker & Docker Compose.
*   API Keys for **AvalAI**, **Tavily**, and optionally **Cloudflare**/**OpenRouter**.

### 1. Clone & Configure
```bash
git clone https://github.com/abtn/nexus-council.git
cd nexus-council
cp .env.example .env
nano .env  # Add your API keys
```

### 2. Environment Variables
```env
# Required
AVALAI_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here

# Optional (Cloudflare)
CF_ACCOUNT_ID=your_account_id
CF_API_TOKEN=your_token

# Optional (OpenRouter)
OPENROUTER_API_KEY=your_key

# Infrastructure (Defaults usually fine for Docker)
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/nexus_council
REDIS_URL=redis://redis:6379/0
```

### 3. Launch
```bash
# Build and start all services
docker-compose up --build -d

# View logs
docker-compose logs -f api worker
```

### 4. Access
*   **Dashboard:** http://localhost:8501
*   **API Docs:** http://localhost:8000/docs

---

## 🎮 Usage Guide

### 1. Select Strategy
*   **Standard Council:** Creates diverse experts (Historian, Economist, etc.) for a broad overview.
*   **Decomposition:** Breaks complex queries into sub-queries for deep analysis.
*   **Quick:** Direct LLM answer without web search (fastest).

### 2. Configure Models
*   **Architect:** Needs strong logic (Recommend: `avalai/gemini-2.0-flash-lite`).
*   **Moderator:** Needs large context window to read all reports (Recommend: `avalai/gemma-3-27b-it`).
*   *Note:* Cloudflare models are great for speed but may trigger fallbacks for complex JSON tasks.

### 3. Analyze Results
*   **Consensus:** The agreed-upon executive summary.
*   **Friction:** Disagreements between experts or missing data.
*   **Recommendations:** Actionable advice.

---

## 🔧 Architecture

```
┌─────────────┐
│  Dashboard  │ (Streamlit)
└──────┬──────┘
       │ HTTP/JSON
       ▼
┌─────────────────┐       ┌──────────────┐
│   FastAPI       │────▶ │  PostgreSQL  │
│   (Orchestrator)│       │  + pgvector  │
└────────┬────────┘       └──────────────┘
         │
         ▼
┌─────────────────┐
│     Redis       │ (Broker)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  ARQ Workers    │
│  (Async Jobs)   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│      External Services          │
│  ┌──────────┐  ┌─────────────┐  │
│  │ Tavily   │  │  LLMs       │  │
│  │ (Search) │  │  (AvalAI/   │  │
│  └──────────┘  │   CF/OR)    │  │
│                └─────────────┘  │
└─────────────────────────────────┘
```

---

## 🐛 Troubleshooting

### Error: `403 Forbidden` during scraping
*   **Cause:** Websites blocking VPN/Data-center IPs.
*   **Fix:** The system now uses browser headers to spoof requests. If some sites still fail, they are likely hard-blocked. The system logs the failure and continues with other sources.

### Error: `413 Payload Too Large`
*   **Cause:** Using Cloudflare (which has smaller input limits) as the **Moderator** for long reports. The fallback prompt (Schema + Reports) becomes too large.
*   **Fix:** Switch the **Moderator** model to `avalai/gemma-3-27b-it` or `avalai/gemini-2.0-flash-lite` in the sidebar settings. These have larger context windows.

### Error: `Developer instruction is not enabled`
*   **Cause:** Using AvalAI Gemma models which reject the standard `system` message role.
*   **Fix:** The system handles this automatically by merging the system prompt into the user prompt. You can ignore this warning in logs.

### Worker not processing tasks?
*   Check Redis connection: `docker-compose logs redis`.
*   Check worker logs: `docker-compose logs worker`.

---

## 🤝 Contributing
Contributions welcome! Priority areas:
*   Additional LLM provider integrations (Anthropic, Local Ollama).
*   Enhanced scraping bypasses (Selenium/Playwright fallback).
*   WebSocket support for real-time dashboard updates.

---

## 🙏 Acknowledgments
*   [FastAPI](https://fastapi.tiangolo.com/)
*   [Streamlit](https://streamlit.io/)
*   [Instructor](https://instructor.site/)
*   [Tavily](https://tavily.com/)