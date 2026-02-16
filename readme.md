# 🏛️ Nexus Council

Nexus Council is a sophisticated autonomous "Council of Experts" system. It mimics a high-level human research and debate process by orchestrating multiple specialized AI agents to solve complex queries.

### 🚀 Capabilities
- **Autonomous Architecture:** An AI "Architect" designs a bespoke team of experts (3-5 agents) specifically tailored to the user's prompt.
- **Parallel Research:** AI "Hunters" perform real-time web research simultaneously using Tavily and Trafilatura.
- **Local RAG (Retrieval-Augmented Generation):** High-speed local embeddings using `all-MiniLM-L6-v2` and `pgvector` allow agents to find needles in haystacks of scraped data.
- **Conflict Resolution:** A "Moderator" analyzes all expert reports to identify "Friction Points" where experts disagree, providing a nuanced final consensus.
- **Real-time Dashboard:** A Streamlit-based UI to track agent progress (Searching 🔵 -> Analyzing 🟠 -> Completed 🟢).

### 🛠️ Tech Stack
- **Backend:** FastAPI, SQLAlchemy 2.0 (Async), Pydantic V2
- **Intelligence:** Multi-provider support (AvalAI, Cloudflare, OpenRouter)
- **Task Orchestration:** Celery + Redis
- **Vector Search:** PostgreSQL + `pgvector`
- **Embeddings:** Local CPU-optimized `sentence-transformers`
- **Frontend:** Streamlit

### 🔧 Stability & Performance Optimizations
- **CPU-Optimized Docker:** Custom build logic to keep images small (~750MB) and prevent WSL2 crashes by using CPU-only Torch.
- **WSL2 Networking:** Custom MTU (Maximum Transmission Unit) settings in Docker Networking to prevent SSL/EOF connection errors.
- **Race Condition Protection:** Explicit database flushing to ensure agents are persistent before research tasks begin.

### 📈 Current Status: Phase 5 (Production Ready)
- **Phase 1-3:** Orchestration & Synthesis (Complete)
- **Phase 4:** Local RAG & Vector Storage (Complete)
- **Phase 5:** Interactive Dashboard & Infrastructure Hardening (Complete)